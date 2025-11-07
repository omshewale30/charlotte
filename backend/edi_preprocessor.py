import os
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime
import PyPDF2
from dataclasses import dataclass
from io import BytesIO

# Azure Blob support
from azure.azure_blob_container_client import AzureBlobContainerClient

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
    
    def __init__(self):
        # Azure configuration
        self.azure_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
        self.azure_source_container = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "")
        
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
        
    

    def extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes (downloaded from Azure Blob)."""
        try:
            with BytesIO(pdf_bytes) as byte_stream:
                reader = PyPDF2.PdfReader(byte_stream)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            logger.error(f"Error reading PDF from bytes: {e}")
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
    
    

