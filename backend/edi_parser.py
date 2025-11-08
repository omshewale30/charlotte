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
        self.search_service = EDISearchService()

    def parse_edi_file(self, file_path: str, filename: Optional[str] = None) -> Dict:
        """
        Parse a single EDI file and extract transactions.
        
        Args:
            file_path: Path to the EDI file (PDF)
            filename: Optional filename to use in transaction records (defaults to basename of file_path)
            
        Returns:
            Dictionary containing:
                - transactions: List of transaction dictionaries
                - file_name: The filename used
                - transaction_count: Number of transactions extracted
                
        Raises:
            DuplicateReportError: If transactions from this file already exist in the search index
            ValueError: If the file cannot be parsed or contains no transactions
        """
        if filename is None:
            filename = os.path.basename(file_path)
        
        logger.info(f"Parsing EDI file: {filename}")
        
        # Check if file already exists in search index
        if self.search_service.check_if_file_exists(filename):
            logger.warning(f"File {filename} already exists in search index")
            raise DuplicateReportError(
                f"Transactions from file '{filename}' already exist in the search index"
            )
        
        try:
            # Read the file
            with open(file_path, 'rb') as f:
                pdf_bytes = f.read()
            
            # Extract text and transactions
            text = self.extractor.extract_text_from_pdf_bytes(pdf_bytes)
            if not text:
                raise ValueError(f"No text extracted from {filename}")
            
            pages = self.extractor.split_pages(text)
            transactions = []
            
            for page_text in pages:
                if 'PAYMENT INFORMATION:' in page_text and 'CREDIT:' in page_text:
                    transaction = self.extractor.parse_page_content(page_text, filename)
                    if transaction:
                        transactions.append(transaction.to_dict())
            
            if not transactions:
                raise ValueError(f"No transactions found in {filename}")
            
            logger.info(f"Extracted {len(transactions)} transactions from {filename}")
            
            return {
                "transactions": transactions,
                "file_name": filename,
                "transaction_count": len(transactions)
            }
            
        except DuplicateReportError:
            # Re-raise duplicate errors
            raise
        except Exception as e:
            logger.error(f"Error parsing {filename}: {e}")
            raise ValueError(f"Failed to parse EDI file {filename}: {str(e)}")
    
    def index_transactions(self, transactions: List[Dict], file_name: str) -> bool:
        """
        Index transactions into the search index.
        
        Args:
            transactions: List of transaction dictionaries
            file_name: The filename associated with these transactions
            
        Returns:
            True if indexing was successful, False otherwise
        """
        if not transactions:
            logger.warning("No transactions to index")
            return False
        
        try:
            # Get current highest ID from search index to continue numbering
            current_stats = self.search_service.get_statistics()
            current_count = current_stats.get('total_transactions', 0)
            
            # Prepare documents for search index
            search_documents = []
            for i, transaction in enumerate(transactions, start=current_count + 1):
                doc = {
                    "id": str(i),
                    "trace_number": transaction.get("trace_number", ""),
                    "amount": transaction.get("amount", 0.0),
                    "effective_date": transaction.get("effective_date", ""),
                    "receiver": transaction.get("receiver", ""),
                    "originator": transaction.get("originator", ""),
                    "page_number": transaction.get("page_number", ""),
                    "routing_id_credit": transaction.get("routing_id_credit", ""),
                    "routing_id_debit": transaction.get("routing_id_debit", ""),
                    "company_id_debit": transaction.get("company_id_debit", ""),
                    "mutually_defined": transaction.get("mutually_defined", ""),
                    "file_name": transaction.get("file_name", file_name),
                    "searchable_text": f"{transaction.get('amount', 0)} {transaction.get('effective_date', '')} {transaction.get('receiver', '')} {transaction.get('originator', '')} {transaction.get('trace_number', '')}"
                }
                search_documents.append(doc)
            
            # Upload to search index
            success = self.search_service.upload_documents(search_documents)
            
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
