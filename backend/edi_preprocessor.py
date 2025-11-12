import os
import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import PyPDF2
from dataclasses import dataclass, field
from io import BytesIO
import json
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CHS_ORIGINATORS = { 
"BCBS of NC",
"BCBS-NC",
"BCBSNC ASO",
"BCBSNC Host",
"CAMPUS HEALTH PHARMACY",
"CIGNA",
"CIGNA EDGE TRANS",
"GEHA UMR",
"Golden Rule Insurance",
"Medica",
"National Foundation",
"NORTH CAROLINA S",
"OXFORD HEALTH IN",
"STUDENT RESOURCE",
"UHC Benefits Pla",
"UHC COMMUNITY PL",
"UMR",
"UMR USNAS",
"UNITED HEALTHCARE",
"UNITEDHEALTHCARE",
    }

@dataclass
class EDITransactionLineItem:
    """
    Data class for EDI transaction line items (found in ACHCTX formats).
    These correspond to the "DETAILS" section of the master report.
    """
    line_number: str
    seller_invoice_num: str
    invoice_amount: float
    net_amount_paid: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "line_number": self.line_number,
            "seller_invoice_num": self.seller_invoice_num,
            "invoice_amount": self.invoice_amount,
            "net_amount_paid": self.net_amount_paid,
        }

@dataclass
class EDITransaction:
    """
    Unified data class for EDI transactions (handles both ACHCCD+ and ACHCTX).
    """
    # Core fields
    trace_number: str
    amount: float
    effective_date: str
    receiver: str
    originator: str
    input_format: str
    file_name: str
    
    # Party details
    routing_id_credit: str
    demand_account_credit: str
    routing_id_debit: str
    company_id_debit: str
    
    # Optional/Misc
    page_number: str  # Page where the payment *starts*
    mutually_defined: str
    
    # Hierarchical data for ACHCTX
    line_items: List[EDITransactionLineItem] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "trace_number": self.trace_number,
            "amount": self.amount,
            "effective_date": self.effective_date,
            "receiver": self.receiver,
            "originator": self.originator,
            "input_format": self.input_format,
            "file_name": self.file_name,
            "routing_id_credit": self.routing_id_credit,
            "demand_account_credit": self.demand_account_credit,
            "routing_id_debit": self.routing_id_debit,
            "company_id_debit": self.company_id_debit,
            "page_number": self.page_number,
            "mutually_defined": self.mutually_defined,
            "line_items": [item.to_dict() for item in self.line_items]
        }


class EDITransactionExtractor:
    """
    Extracts transaction data from EDI PDF reports.
    
    Handles both ACHCCD+ (Current-EDI-sample) and ACHCTX (Master-EDI-sample)
    formats by splitting by 'PAYMENT INFORMATION:' rather than by page.
    """
    
    def __init__(self):
        # Regex patterns for extracting data
        self.patterns = {
            # --- Universal Patterns ---
            'payment_split': r'PAYMENT INFORMATION:',
            'credit_amount': r'CREDIT:\s*\$?([\d,]+\.?\d*)',
            'effective_date': r'EFFECTIVE DATE:\s*(\d{2}/\d{2}/\d{4})',
            'input_format': r'INPUT FORMAT:\s*([A-Z0-9+]+)',
            'page_number': r'PAGE:\s*(\d+)',
            'routing_id': r'ROUTING ID:\s*(\d+)',
            'demand_acct': r'DEMAND ACCT:\s*(\d+)',
            'company_id': r'COMPANY ID:\s*([A-Za-z0-9]+)',
            'originator': r'ORIGINATOR:\s*([^\n]+)', # Grabs the first line
            'receiver': r'RECEIVER:\s*([^\n]+)',   # Grabs the first line

            # --- ACHCCD+ (Current) Specific ---
            'trace_number_ccd': r'TRACE NUMBER:\s*([A-Za-z0-9]+)',
            'mutually_defined': r'MUTUALLY DEFINED:\s*(\d+)',
            
            # --- ACHCTX (Master) Specific ---
            'credit_party_block': r'CREDIT PARTY(.*?)(?:DEBIT PARTY|REMITTANCE INFORMATION|====)',
            'debit_party_block': r'DEBIT PARTY(.*?)(?:REMITTANCE INFORMATION:|TRACE NUMBER:|====|PAGE:)',
            'trace_number_ctx': r'TRACE NUMBER:\s*(\d+)', # The first, simpler trace number
            'details_block': r'DETAILS:(.*?)(?:PAYMENT INFORMATION:|$)',
            'line_item_split': r'LINE:\s*(\d{5})',
            'line_invoice_num': r'SELLER INVOICE NUM:\s*(.*?)\n',
            'line_amount_paid': r'AMOUNT PAID:\s*(.*?)\n',
            'line_invoice_amount': r'TOTAL INV AMOUNT:\s*(.*?)\n'
        }

    def _search(self, pattern_name: str, text: str, flags=0) -> str:
        """Helper function to search for a pattern and return group 1 or empty string."""
        match = re.search(self.patterns[pattern_name], text, flags)
        return match.group(1).strip() if match else ""

    def _clean_amount(self, amount_str: str) -> float:
        """Converts a formatted string amount to a float."""
        if not amount_str:
            return 0.0
        try:
            return float(amount_str.replace('$', '').replace(',', ''))
        except ValueError:
            return 0.0

    def _format_date(self, date_str: str) -> str:
        """Convert MM/DD/YYYY to YYYY-MM-DD format"""
        try:
            if date_str and '/' in date_str:
                date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                return date_obj.strftime('%Y-%m-%d')
        except Exception:
            pass
        return date_str

    def extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes (downloaded from Azure Blob)."""
        try:
            with BytesIO(pdf_bytes) as byte_stream:
                reader = PyPDF2.PdfReader(byte_stream)
                text = ""
                for page in reader.pages:
                    # Add a separator to mark page breaks, which helps parsing
                    text += page.extract_text() + "\n---PAGE BREAK---\n"
                return text
        except Exception as e:
            logger.error(f"Error reading PDF from bytes: {e}")
            return ""

    def parse_edi_file(self, pdf_bytes: bytes, file_name: str) -> Tuple[List[EDITransaction], List[EDITransaction], Dict[str, float], Dict[str, float]]:
        """
        Main parsing function. Splits file by payment and routes to correct parser.
        Returns a tuple of lists: (all transactions, CHS transactions)
        """
        full_text = self.extract_text_from_pdf_bytes(pdf_bytes)
        if not full_text:
            return []

        # TODO:make the list a dictionary of trace number: amount"

        all_transactions = []
        all_trace_numbers = {}
        chs_transactions = []
        chs_trace_numbers = {}
        
        # Split the entire document by "PAYMENT INFORMATION:"
        # This correctly groups multi-page transactions.
        payment_chunks = re.split(self.patterns['payment_split'], full_text, flags=re.DOTALL)
        
        for chunk in payment_chunks[1:]:  # Skip the header chunk
            input_format = self._search('input_format', chunk)
            
            if input_format == 'ACHCCD+' or input_format == 'ACHCCD':
                transaction = self._parse_ccd_chunk(chunk, file_name)
            elif input_format == 'ACHCTX':
                transaction = self._parse_ctx_chunk(chunk, file_name)
            else:
                logger.warning(f"Skipping chunk with unknown INPUT FORMAT: {input_format}")
                transaction = None
                
            if transaction:
                all_transactions.append(transaction)
                all_trace_numbers[transaction.trace_number] = transaction.amount
            if transaction and transaction.originator in CHS_ORIGINATORS:
                #delete the 'line_items' from the transaction
                transaction.line_items = []

                chs_transactions.append(transaction)
                chs_trace_numbers[transaction.trace_number] = transaction.amount
    
        return all_transactions, chs_transactions, all_trace_numbers, chs_trace_numbers

    def _parse_ccd_chunk(self, chunk: str, file_name: str) -> Optional[EDITransaction]:
        """Parses a payment chunk identified as ACHCCD+ (Current-EDI-sample format)."""
        try:
            amount_str = self._search('credit_amount', chunk)
            if not amount_str:
                return None  # Not a valid transaction

            amount = self._clean_amount(amount_str)
            effective_date = self._format_date(self._search('effective_date', chunk))
            page_number = self._search('page_number', chunk)
            
            # In CCD+, routing IDs are sequential. Credit is first, Debit is second.
            routing_ids = re.findall(self.patterns['routing_id'], chunk)
            routing_id_credit = routing_ids[0] if len(routing_ids) > 0 else ""
            routing_id_debit = routing_ids[1] if len(routing_ids) > 1 else ""
            
            # Demand account is for the credit party
            demand_acct = self._search('demand_acct', chunk) 
            
            # Company ID is for the debit party
            company_ids = re.findall(self.patterns['company_id'], chunk)
            company_id_debit = company_ids[1] if len(company_ids) > 1 else (company_ids[0] if company_ids else "")
            
            trace_number = self._search('trace_number_ccd', chunk)
            receiver = self._search('receiver', chunk)
            originator = self._search('originator', chunk)
            mutually_defined = self._search('mutually_defined', chunk)
            input_format = self._search('input_format', chunk)

            return EDITransaction(
                trace_number=trace_number,
                amount=amount,
                effective_date=effective_date,
                receiver=receiver.replace('MUTUALLY DEFINED:', '').strip(),
                originator=originator,
                page_number=page_number,
                routing_id_credit=routing_id_credit,
                routing_id_debit=routing_id_debit,
                company_id_debit=company_id_debit,
                mutually_defined=mutually_defined,
                input_format=input_format,
                demand_account_credit=demand_acct,
                file_name=file_name,
            )
        except Exception as e:
            logger.error(f"Error parsing ACHCCD+ chunk: {e}")
            return None

    def _parse_ctx_chunk(self, chunk: str, file_name: str) -> Optional[EDITransaction]:
        """Parses a payment chunk identified as ACHCTX (Master-EDI-sample format)."""
        try:
            amount_str = self._search('credit_amount', chunk)
            if not amount_str:
                return None

            amount = self._clean_amount(amount_str)
            effective_date = self._format_date(self._search('effective_date', chunk))
            page_number = self._search('page_number', chunk) # Page where payment starts
            
            # Isolate Credit and Debit party blocks for safer parsing
            credit_block = self._search('credit_party_block', chunk, re.DOTALL)
            debit_block = self._search('debit_party_block', chunk, re.DOTALL)

            routing_id_credit = self._search('routing_id', credit_block)
            demand_account_credit = self._search('demand_acct', credit_block)
            
            routing_id_debit = self._search('routing_id', debit_block)
            company_id_debit = self._search('company_id', debit_block)

            trace_number = self._search('trace_number_ctx', chunk)
            receiver = self._search('receiver', chunk)
            originator = self._search('originator', chunk)

            # Parse the line items from the "DETAILS" section
            line_items = self._parse_ctx_line_items(chunk)

            return EDITransaction(
                trace_number=trace_number,
                amount=amount,
                effective_date=effective_date,
                receiver=receiver,
                originator=originator,
                page_number=page_number,
                routing_id_credit=routing_id_credit,
                routing_id_debit=routing_id_debit,
                company_id_debit=company_id_debit,
                mutually_defined="", # Not present in CTX
                input_format="ACHCTX",
                demand_account_credit=demand_account_credit,
                file_name=file_name,
                line_items=line_items
            )
        except Exception as e:
            logger.error(f"Error parsing ACHCTX chunk: {e}")
            return None

    def _parse_ctx_line_items(self, chunk: str) -> List[EDITransactionLineItem]:
        """Parses the 'DETAILS:' block for line items."""
        items = []
        details_block_match = re.search(self.patterns['details_block'], chunk, re.DOTALL)
        
        if not details_block_match:
            return items
            
        details_text = details_block_match.group(1)
        
        # Split the DETAILS block by 'LINE: XXXXX'
        # This results in a list like: ['<line_num_1>', '<content_1>', '<line_num_2>', '<content_2>']
        line_chunks = re.split(self.patterns['line_item_split'], details_text, flags=re.DOTALL)[1:]

        # Iterate over the list 2 items at a time
        for i in range(0, len(line_chunks), 2):
            try:
                line_number = line_chunks[i].strip()
                line_content = line_chunks[i+1]
                
                invoice_num = self._search('line_invoice_num', line_content).replace('\n', ' ').strip()
                amount_paid_str = self._search('line_amount_paid', line_content)
                invoice_amount_str = self._search('line_invoice_amount', line_content)
                
                item = EDITransactionLineItem(
                    line_number=line_number,
                    seller_invoice_num=invoice_num,
                    net_amount_paid=self._clean_amount(amount_paid_str),
                    invoice_amount=self._clean_amount(invoice_amount_str)
                )
                items.append(item)
            except Exception as e:
                logger.warning(f"Failed to parse line item in chunk: {e}")
                
        return items
    


def main():
    """Main function to test the parser."""
    from pathlib import Path
    
    parser = EDITransactionExtractor()
    
    # Get the script directory and navigate to documents folder (one directory up)
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent  # Go up one level from edi_preprocessor.py to backend/
    pdf_path = backend_dir / "documents" / "Mixed.pdf"
    
    if not pdf_path.exists():
        print(f"Error: PDF file not found at {pdf_path}")
        return
    
    print(f"Parsing PDF: {pdf_path}")
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    all_transactions, chs_transactions, all_trace_numbers, chs_trace_numbers = parser.parse_edi_file(pdf_bytes, pdf_path.name)
    print(f"✓ Parsed {len(all_transactions)} all transactions")
    print(f"✓ Parsed {len(chs_transactions)} CHS transactions")
    # Save to JSON in the same directory as the script
    all_transactions_dict = [transaction.to_dict() for transaction in all_transactions]
    chs_transactions_dict = [transaction.to_dict() for transaction in chs_transactions]
    output_json_path = script_dir / "all_transactions.json"
    chs_output_json_path = script_dir / "chs_transactions.json"

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_transactions_dict, f, indent=2, ensure_ascii=False)
    
    with open(chs_output_json_path, 'w', encoding='utf-8') as f:
        json.dump(chs_transactions_dict, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved all transactions to {output_json_path}")
    print(f"✓ Saved CHS transactions to {chs_output_json_path}")

if __name__ == "__main__":
    main()