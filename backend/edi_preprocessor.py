import os
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import PyPDF2
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Transaction:
    """Data class for EDI transaction"""
    trace_number: str
    amount: float
    effective_date: str
    receiver: str
    originator: str
    page_number: str
    routing_id_credit: str
    routing_id_debit: str
    company_id_debit: str
    mutually_defined: str
    input_format: str
    demand_account: str
    file_name: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "trace_number": self.trace_number,
            "amount": self.amount,
            "effective_date": self.effective_date,
            "receiver": self.receiver,
            "originator": self.originator,
            "page_number": self.page_number,
            "routing_id_credit": self.routing_id_credit,
            "routing_id_debit": self.routing_id_debit,
            "company_id_debit": self.company_id_debit,
            "mutually_defined": self.mutually_defined,
            "input_format": self.input_format,
            "demand_account": self.demand_account,
            "file_name": self.file_name
        }

class EDITransactionExtractor:
    """Extract transaction data from EDI PDF reports"""
    
    def __init__(self, documents_dir: str = "./documents", output_dir: str = "./processed_data"):
        self.documents_dir = Path(documents_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Regex patterns for extracting data
        self.patterns = {
            'credit_amount': r'CREDIT:\s*\$?([\d,]+\.?\d*)',
            'effective_date': r'EFFECTIVE DATE:\s*(\d{2}/\d{2}/\d{4})',
            'page_number': r'PAGE:\s*(\d+)',
            'routing_id_credit': r'ROUTING ID:\s*(\d+)',
            'demand_acct': r'DEMAND ACCT:\s*(\d+)',
            'company_id': r'COMPANY ID:\s*(\d+)',
            'trace_number': r'TRACE NUMBER:\s*([A-Za-z0-9]+)',
            'originating_co_id': r'ORIGINATING CO ID:\s*(\d+)',
            'receiver': r'RECEIVER:\s*([A-Za-z0-9\s/]+?)(?:\n|MUTUALLY)',
            'mutually_defined': r'MUTUALLY DEFINED:\s*(\d+)',
            'originator': r'ORIGINATOR:\s*([A-Za-z0-9\s\-/]+?)(?:\n|$)'
        }
    
    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from PDF file"""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            logger.error(f"Error reading PDF {pdf_path}: {e}")
            return ""
    
    def parse_page_content(self, page_text: str, file_name: str) -> Optional[Transaction]:
        """Parse a single page to extract transaction data"""
        try:
            # Extract all required fields
            credit_match = re.search(self.patterns['credit_amount'], page_text)
            if not credit_match:
                return None
            
            amount_str = credit_match.group(1).replace(',', '')
            amount = float(amount_str)
            
            # Extract other fields
            effective_date = self._extract_field(page_text, 'effective_date')
            page_number = self._extract_field(page_text, 'page_number')
            
            # Get routing IDs (first one is credit, second is debit)
            routing_ids = re.findall(self.patterns['routing_id_credit'], page_text)
            routing_id_credit = routing_ids[0] if len(routing_ids) > 0 else ""
            routing_id_debit = routing_ids[1] if len(routing_ids) > 1 else ""
            
            demand_acct = self._extract_field(page_text, 'demand_acct')
            
            # Get company IDs (debit party company ID)
            company_ids = re.findall(self.patterns['company_id'], page_text)
            company_id_debit = company_ids[1] if len(company_ids) > 1 else (company_ids[0] if company_ids else "")
            
            # Get trace numbers (first one is the primary)
            trace_numbers = re.findall(self.patterns['trace_number'], page_text)
            trace_number = trace_numbers[0] if trace_numbers else ""
            
            receiver = self._extract_field(page_text, 'receiver', clean_receiver=True)
            mutually_defined = self._extract_field(page_text, 'mutually_defined')
            originator = self._extract_field(page_text, 'originator', clean_originator=True)
            
            # Convert date format from MM/DD/YYYY to YYYY-MM-DD
            formatted_date = self._format_date(effective_date)
            
            return Transaction(
                trace_number=trace_number,
                amount=amount,
                effective_date=formatted_date,
                receiver=receiver,
                originator=originator,
                page_number=page_number,
                routing_id_credit=routing_id_credit,
                routing_id_debit=routing_id_debit,
                company_id_debit=company_id_debit,
                mutually_defined=mutually_defined,
                input_format="ACHCCD+",  # This appears to be standard
                demand_account=demand_acct,
                file_name=file_name
            )
            
        except Exception as e:
            logger.error(f"Error parsing page content: {e}")
            return None
    
    def _extract_field(self, text: str, field_name: str, clean_receiver: bool = False, clean_originator: bool = False) -> str:
        """Extract a field using regex pattern"""
        match = re.search(self.patterns[field_name], text, re.MULTILINE)
        if match:
            value = match.group(1).strip()
            if clean_receiver and field_name == 'receiver':
                # Clean up receiver field
                value = re.sub(r'\s+', ' ', value).strip()
                value = value.replace('MUTUALLY DEFINED:', '').strip()
            elif clean_originator and field_name == 'originator':
                # Clean up originator field
                value = re.sub(r'\s+', ' ', value).strip()
            return value
        return ""
    
    def _format_date(self, date_str: str) -> str:
        """Convert MM/DD/YYYY to YYYY-MM-DD format"""
        try:
            if date_str and '/' in date_str:
                date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                return date_obj.strftime('%Y-%m-%d')
        except:
            pass
        return date_str
    
    def split_pages(self, text: str) -> List[str]:
        """Split PDF text into individual pages"""
        # Split by page headers
        page_pattern = r'NORTH CAROLINA STATE TREASURER.*?PAGE:\s*\d+'
        pages = re.split(page_pattern, text)
        
        # Re-add headers to pages (except first empty split)
        headers = re.findall(page_pattern, text)
        
        result_pages = []
        for i, page_content in enumerate(pages[1:], 0):
            if i < len(headers):
                full_page = headers[i] + page_content
                result_pages.append(full_page)
        
        return result_pages
    
    def process_file(self, pdf_path: Path) -> List[Transaction]:
        """Process a single PDF file and extract all transactions"""
        logger.info(f"Processing file: {pdf_path.name}")
        
        text = self.extract_text_from_pdf(pdf_path)
        if not text:
            return []
        
        pages = self.split_pages(text)
        transactions = []
        
        for page_text in pages:
            if 'PAYMENT INFORMATION:' in page_text and 'CREDIT:' in page_text:
                transaction = self.parse_page_content(page_text, pdf_path.name)
                if transaction:
                    transactions.append(transaction)
        
        logger.info(f"Extracted {len(transactions)} transactions from {pdf_path.name}")
        return transactions
    
    def process_all_files(self) -> List[Transaction]:
        """Process all PDF files in the documents directory"""
        all_transactions = []
        
        if not self.documents_dir.exists():
            logger.error(f"Documents directory {self.documents_dir} does not exist")
            return []
        
        pdf_files = list(self.documents_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        for pdf_file in pdf_files:
            transactions = self.process_file(pdf_file)
            all_transactions.extend(transactions)
        
        return all_transactions
    
    def save_transactions(self, transactions: List[Transaction], output_filename: str = "edi_transactions.json"):
        """Save transactions to JSON file"""
        output_path = self.output_dir / output_filename
        
        transactions_dict = [t.to_dict() for t in transactions]
        
        with open(output_path, 'w') as f:
            json.dump(transactions_dict, f, indent=2)
        
        logger.info(f"Saved {len(transactions)} transactions to {output_path}")
        return output_path
    
    def create_search_index_data(self, transactions: List[Transaction]) -> Dict:
        """Create data structure optimized for Azure AI Search indexing"""
        search_documents = []
        
        for i, transaction in enumerate(transactions):
            doc = {
                "id": str(i + 1),  # Azure Search requires string ID
                "trace_number": transaction.trace_number,
                "amount": transaction.amount,
                "effective_date": transaction.effective_date,
                "receiver": transaction.receiver,
                "originator": transaction.originator,
                "page_number": transaction.page_number,
                "routing_id_credit": transaction.routing_id_credit,
                "routing_id_debit": transaction.routing_id_debit,
                "company_id_debit": transaction.company_id_debit,
                "mutually_defined": transaction.mutually_defined,
                "file_name": transaction.file_name,
                # Create searchable text field combining key information
                "searchable_text": f"{transaction.amount} {transaction.effective_date} {transaction.receiver} {transaction.originator} {transaction.trace_number}"
            }
            search_documents.append(doc)
        
        return {
            "documents": search_documents,
            "total_count": len(search_documents)
        }

def main():
    """Main function to run the preprocessor"""
    extractor = EDITransactionExtractor()
    
    # Process all EDI files
    transactions = extractor.process_all_files()
    
    if transactions:
        # Save raw transaction data
        json_path = extractor.save_transactions(transactions)
        
        # Create search-optimized data
        search_data = extractor.create_search_index_data(transactions)
        search_path = extractor.output_dir / "search_index_data.json"
        
        with open(search_path, 'w') as f:
            json.dump(search_data, f, indent=2)
        
        logger.info(f"Created search index data at {search_path}")
        
        # Print summary
        print(f"\n--- Processing Summary ---")
        print(f"Total transactions extracted: {len(transactions)}")
        print(f"Data saved to: {json_path}")
        print(f"Search index data: {search_path}")
        
        # Show sample transaction
        if transactions:
            print(f"\n--- Sample Transaction ---")
            sample = transactions[0]
            print(f"Trace Number: {sample.trace_number}")
            print(f"Amount: ${sample.amount}")
            print(f"Date: {sample.effective_date}")
            print(f"Originator: {sample.originator}")
            print(f"Receiver: {sample.receiver}")
    else:
        print("No transactions found in the documents directory")

if __name__ == "__main__":
    main()