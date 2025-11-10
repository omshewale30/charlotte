"""
EDI Parser for processing EDI transaction files
This module parses EDI PDF files and extracts transaction data.
"""

import os
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

from edi_preprocessor import EDITransactionExtractor
from azure.azure_search_setup import EDISearchService
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DuplicateReportError(Exception):
    """Exception raised when a report already exists in the search index"""
    pass


class EDIParser:
    """Parses EDI files and extracts transaction data"""

    def __init__(self):
        load_dotenv()

        # Initialize processors
        self.extractor = EDITransactionExtractor()
        self.chs_edi_search_service = EDISearchService(index_name="edi-transactions")
        self.master_edi_search_service = EDISearchService(index_name="master-edi")

    def parse_edi_file(self, file_path: str, filename: Optional[str] = None) -> Dict:
        """
        Parse a single EDI file and extract transactions.
        
        Args:
            file_path: Path to the EDI file (PDF)
            filename: Optional filename to use in transaction records (defaults to basename of file_path)
            
        Returns:
            Dictionary containing:
                - all_transactions: List of all transaction dictionaries
                - chs_transactions: List of CHS transaction dictionaries (may be empty)
                - file_name: The filename used
                - all_transaction_count: Number of all transactions extracted
                - chs_transaction_count: Number of CHS transactions extracted
                - chs_duplicate: Boolean indicating if CHS trace numbers already exist in index
                
        Raises:
            DuplicateReportError: If the entire file already exists in the search index (file-level duplicate)
            ValueError: If the file cannot be parsed or contains no transactions
        """
        if filename is None:
            filename = os.path.basename(file_path)
        
        logger.info(f"Parsing EDI file: {filename}")
        
        # Check if file already exists in search index (file-level duplicate check)
        # If the entire file exists, we should not proceed at all
        if self.chs_edi_search_service.check_if_file_exists(filename):
            logger.warning(f"File {filename} already exists in CHS search index")
            raise DuplicateReportError(
                f"Transactions from file '{filename}' already exist in the CHS search index"
            )
        
        if self.master_edi_search_service.check_if_file_exists(filename):
            logger.warning(f"File {filename} already exists in Master EDI search index")
            raise DuplicateReportError(
                f"Transactions from file '{filename}' already exist in the Master EDI search index"
            )
        
        try:
            # Read the file
            with open(file_path, 'rb') as f:
                pdf_bytes = f.read()
            

            all_transactions, chs_transactions, chs_trace_numbers = self.extractor.parse_edi_file(pdf_bytes, filename)
            if not all_transactions:
                raise ValueError(f"No all transactions found in {filename}")

            # Convert EDITransaction objects to dictionaries
            all_transactions_dict = [t.to_dict() for t in all_transactions]
            chs_transactions_dict = [t.to_dict() for t in chs_transactions] if chs_transactions else []

            # Check if any CHS trace numbers already exist in the CHS search index
            # This is a trace-number-level duplicate check (not file-level)
            chs_duplicate = False
            if chs_trace_numbers:
                try:
                    if self.chs_edi_search_service.check_if_trace_numbers_exist(chs_trace_numbers):
                        logger.warning(f"CHS transactions with trace numbers {chs_trace_numbers} already exist in the CHS search index. CHS transactions will not be indexed, but all_transactions will still be indexed.")
                        chs_duplicate = True
                except Exception as e:
                    # If there's an error checking, log it but don't fail the entire parse
                    logger.error(f"Error checking if CHS trace numbers exist: {e}")
                    # Continue processing - we'll still try to index, but this is a warning

        
            return {
                "all_transactions": all_transactions_dict,
                "chs_transactions": chs_transactions_dict,
                "file_name": filename,
                "all_transaction_count": len(all_transactions_dict),
                "chs_transaction_count": len(chs_transactions_dict),
                "chs_duplicate": chs_duplicate
            }
            
        except DuplicateReportError:
            # Re-raise duplicate errors (file-level duplicates)
            raise
        except Exception as e:
            logger.error(f"Error parsing {filename}: {e}")
            raise ValueError(f"Failed to parse EDI file {filename}: {str(e)}")
    
    def index_transactions(self, transactions: List[Dict], file_name: str, index_name: str) -> bool:
        """
        Index transactions into the search index.
        
        Args:
            transactions: List of transaction dictionaries
            file_name: The filename associated with these transactions
            index_name: The name of the index to index the transactions into

        Returns:
            True if indexing was successful, False otherwise
        """
        if not transactions:
            logger.warning("No transactions to index")
            return False
        
        try:
            # Prepare documents for search index
            search_documents = []
            for transaction in transactions:
                # Base document with fields common to both indexes
                doc = {
                    "id": str(uuid.uuid4()),
                    "trace_number": transaction.get("trace_number", ""),
                    "amount": transaction.get("amount", 0.0),
                    "effective_date": transaction.get("effective_date", ""),
                    "receiver": transaction.get("receiver", ""),
                    "originator": transaction.get("originator", ""),
                    "file_name": transaction.get("file_name", ""),
                    "routing_id_credit": transaction.get("routing_id_credit", ""),
                    "routing_id_debit": transaction.get("routing_id_debit", ""),
                    "company_id_debit": transaction.get("company_id_debit", ""),
                    "mutually_defined": transaction.get("mutually_defined", ""),
                    "page_number": transaction.get("page_number", ""),
                    "searchable_text": f"{transaction.get('amount', 0)} {transaction.get('effective_date', '')} {transaction.get('receiver', '')} {transaction.get('originator', '')} {transaction.get('trace_number', '')}"
                }
                
                # Add index-specific fields
                if index_name == "edi-transactions":
                    # edi-transactions index schema - only include fields that exist in the index
                    # Remove any fields not in the schema (demand_account_credit, line_items, input_format)
                    pass  # Already have all required fields
                elif index_name == "master-edi":
                    # master-edi index may have additional fields like line_items, demand_account_credit, input_format
                    # Add fields that are specific to master-edi if needed
                    if "demand_account_credit" in transaction:
                        doc["demand_account_credit"] = transaction.get("demand_account_credit", "")
                    if "line_items" in transaction:
                        doc["line_items"] = transaction.get("line_items", [])
                    if "input_format" in transaction:
                        doc["input_format"] = transaction.get("input_format", "")
                
                search_documents.append(doc)
            
            # Upload to search index
            if index_name == "edi-transactions":
                search_service = self.chs_edi_search_service
            elif index_name == "master-edi":
                search_service = self.master_edi_search_service
            else:
                raise ValueError(f"Invalid index name: {index_name}")
            success = search_service.upload_documents(search_documents)

        
            if success:
                logger.info(f"Successfully indexed {len(search_documents)} transactions from {file_name}")
            else:
                logger.error(f"Failed to index transactions from {file_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error indexing transactions: {e}")
            return False


def main():
    """Test the EDI parser"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python edi_parser.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    parser = EDIParser()
    
    try:
        result = parser.parse_edi_file(file_path)
        print(f"Parsed {result['transaction_count']} transactions from {result['file_name']}")
        print(f"First transaction: {result['transactions'][0] if result['transactions'] else 'None'}")
    except DuplicateReportError as e:
        print(f"Duplicate file: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
