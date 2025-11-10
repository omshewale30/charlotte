#!/usr/bin/env python3
"""
Master EDI Report Parser using PyPDF2
Parses master EDI PDF documents and extracts transactions with additional fields like "lines"
"""

import os
import sys
import json
import re
import PyPDF2
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Transaction structure matching edi_preprocessor.py
class Transaction:
    """Data class for EDI transaction (master report with additional fields)"""
    def __init__(self):
        # Standard Transaction fields
        self.trace_number: str = ""
        self.amount: float = 0.0
        self.effective_date: str = ""
        self.receiver: str = ""
        self.originator: str = ""
        self.page_number: str = ""
        self.routing_id_credit: str = ""
        self.routing_id_debit: str = ""
        self.company_id_debit: str = ""
        self.mutually_defined: str = ""
        self.input_format: str = ""
        self.demand_account: str = ""
        self.file_name: str = ""
        # Additional fields for master EDI report
        self.lines: List[Dict] = []  # Line items/details
    
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
            "file_name": self.file_name,
            "lines": self.lines
        }


class MasterEDIReportParser:
    """Parser for master EDI reports with additional fields"""
    
    def __init__(self):
        # Regex patterns for extracting data (similar to edi_preprocessor.py)
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
    
    def _extract_field(self, text: str, field_name: str, clean_receiver: bool = False, clean_originator: bool = False) -> str:
        """Extract a field using regex pattern, ignoring whitespace"""
        match = re.search(self.patterns[field_name], text, re.MULTILINE)
        if match:
            value = match.group(1).strip()
            # Normalize whitespace
            value = re.sub(r'\s+', ' ', value).strip()
            if clean_receiver and field_name == 'receiver':
                value = value.replace('MUTUALLY DEFINED:', '').strip()
            elif clean_originator and field_name == 'originator':
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
    
    def _extract_lines(self, page_text: str) -> List[Dict]:
        """
        Extract line items/details from master EDI report.
        This looks for detail lines that might appear after the main transaction data.
        """
        lines = []
        
        # Common patterns for line items in EDI reports
        # Look for numbered lines, detail sections, or table rows
        # Adjust patterns based on actual PDF structure
        
        # Pattern 1: Look for lines with numbers/amounts/details
        # Example: "1. Description: ... Amount: $XX.XX"
        line_patterns = [
            r'(\d+)\.\s*([^\n]+?)(?:\n|$)',
            r'LINE\s*(\d+):\s*([^\n]+)',
            r'DETAIL\s*(\d+):\s*([^\n]+)',
        ]
        
        # Try to find line items after the main transaction block
        # Look for sections that might contain line details
        detail_section_pattern = r'(?:LINE|DETAIL|ITEM).*?(?=\n\n|\n[A-Z]{2,}:|$)'
        
        # Extract potential line items
        for pattern in line_patterns:
            matches = re.finditer(pattern, page_text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                line_data = {
                    "line_number": match.group(1) if match.lastindex >= 1 else "",
                    "description": match.group(2).strip() if match.lastindex >= 2 else match.group(0).strip(),
                    "raw_text": match.group(0).strip()
                }
                # Normalize whitespace
                for key in line_data:
                    if isinstance(line_data[key], str):
                        line_data[key] = re.sub(r'\s+', ' ', line_data[key]).strip()
                lines.append(line_data)
        
        # If no structured lines found, look for any additional text blocks
        # that might represent line items
        if not lines:
            # Look for text blocks that appear after main transaction fields
            # This is a fallback - adjust based on actual PDF structure
            transaction_end_markers = [
                r'FILE NAME:',
                r'END OF',
                r'PAGE:\s*\d+',
            ]
            
            # Try to extract any remaining structured data as potential lines
            remaining_text = page_text
            for marker in transaction_end_markers:
                parts = re.split(marker, remaining_text, flags=re.IGNORECASE)
                if len(parts) > 1:
                    remaining_text = parts[0]
            
            # Look for any structured data in remaining text
            if remaining_text.strip():
                # Split by common delimiters and create line items
                potential_lines = re.split(r'\n{2,}|\t+', remaining_text)
                for idx, line_text in enumerate(potential_lines, 1):
                    cleaned = re.sub(r'\s+', ' ', line_text).strip()
                    if cleaned and len(cleaned) > 10:  # Only meaningful lines
                        lines.append({
                            "line_number": str(idx),
                            "description": cleaned,
                            "raw_text": cleaned
                        })
        
        return lines
    
    def parse_page_content(self, page_text: str, file_name: str) -> Optional[Transaction]:
        """Parse a single page to extract transaction data with lines"""
        try:
            # Normalize whitespace in page text for better parsing
            page_text = re.sub(r'\s+', ' ', page_text)
            
            # Extract all required fields
            credit_match = re.search(self.patterns['credit_amount'], page_text)
            if not credit_match:
                return None
            
            transaction = Transaction()
            transaction.file_name = file_name
            
            # Extract amount
            amount_str = credit_match.group(1).replace(',', '').replace(' ', '')
            try:
                transaction.amount = float(amount_str)
            except ValueError:
                transaction.amount = 0.0
            
            # Extract other fields
            transaction.effective_date = self._extract_field(page_text, 'effective_date')
            transaction.page_number = self._extract_field(page_text, 'page_number')
            
            # Get routing IDs (first one is credit, second is debit)
            routing_ids = re.findall(self.patterns['routing_id_credit'], page_text)
            transaction.routing_id_credit = routing_ids[0] if len(routing_ids) > 0 else ""
            transaction.routing_id_debit = routing_ids[1] if len(routing_ids) > 1 else ""
            
            transaction.demand_account = self._extract_field(page_text, 'demand_acct')
            
            # Get company IDs (debit party company ID)
            company_ids = re.findall(self.patterns['company_id'], page_text)
            transaction.company_id_debit = company_ids[1] if len(company_ids) > 1 else (company_ids[0] if company_ids else "")
            
            # Get trace numbers (first one is the primary)
            trace_numbers = re.findall(self.patterns['trace_number'], page_text)
            transaction.trace_number = trace_numbers[0] if trace_numbers else ""
            
            transaction.receiver = self._extract_field(page_text, 'receiver', clean_receiver=True)
            transaction.mutually_defined = self._extract_field(page_text, 'mutually_defined')
            transaction.originator = self._extract_field(page_text, 'originator', clean_originator=True)
            
            # Convert date format from MM/DD/YYYY to YYYY-MM-DD
            transaction.effective_date = self._format_date(transaction.effective_date)
            
            # Set default input format
            transaction.input_format = "ACHCCD+"
            
            # Extract line items (additional fields for master EDI report)
            transaction.lines = self._extract_lines(page_text)
            
            return transaction
            
        except Exception as e:
            print(f"Error parsing page content: {e}")
            return None
    
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


def parse_pdf(pdf_path: str, output_json_path: str = None) -> dict:
    """
    Parse a master EDI PDF file and extract transactions with additional fields.
    
    Args:
        pdf_path: Path to the PDF file
        output_json_path: Optional path to save JSON output. If None, auto-generates based on PDF name.
    
    Returns:
        Dictionary containing parsed PDF data with transactions
    """
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        return {}
    
    pdf_file = Path(pdf_path)
    pdf_name = pdf_file.stem
    
    print(f"Parsing Master EDI PDF: {pdf_path}")
    print("=" * 80)
    
    # Initialize parser
    parser = MasterEDIReportParser()
    
    # Initialize output structure
    output_data = {
        "source_file": pdf_file.name,
        "source_path": str(pdf_path),
        "parsed_at": datetime.now().isoformat(),
        "total_pages": 0,
        "total_transactions": 0,
        "transactions": []
    }
    
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            total_pages = len(reader.pages)
            output_data["total_pages"] = total_pages
            
            print(f"Total pages: {total_pages}\n")
            
            # Extract text from all pages
            full_text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
            
            # Split into individual page contents
            pages = parser.split_pages(full_text)
            if not pages:
                # Fallback: use raw pages if split doesn't work
                pages = [page.extract_text() for page in reader.pages if page.extract_text()]
            
            # Parse transactions from each page
            for page_num, page_text in enumerate(pages, start=1):
                print(f"\n{'=' * 80}")
                print(f"Processing Page {page_num} of {total_pages}")
                print(f"{'=' * 80}\n")
                
                if not page_text or not page_text.strip():
                    print("(No text found on this page)")
                    continue
                
                # Check if page contains transaction data
                if 'PAYMENT INFORMATION:' in page_text and 'CREDIT:' in page_text:
                    transaction = parser.parse_page_content(page_text, pdf_file.name)
                    if transaction:
                        transaction_dict = transaction.to_dict()
                        output_data["transactions"].append(transaction_dict)
                        output_data["total_transactions"] += 1
                        print(f"✓ Extracted transaction: Trace #{transaction.trace_number}, Amount: ${transaction.amount}")
                        if transaction.lines:
                            print(f"  - Found {len(transaction.lines)} line item(s)")
                    else:
                        print("⚠ Could not parse transaction from this page")
                else:
                    print("(No transaction data found on this page)")
            
            print(f"\n{'=' * 80}")
            print(f"Finished parsing {total_pages} page(s)")
            print(f"Total transactions extracted: {output_data['total_transactions']}")
            print(f"{'=' * 80}")
            
            # Save to JSON
            if output_json_path is None:
                # Auto-generate output path in the same directory as the PDF
                output_json_path = pdf_file.parent / f"{pdf_name}_parsed.json"
            
            with open(output_json_path, 'w', encoding='utf-8') as json_file:
                json.dump(output_data, json_file, indent=2, ensure_ascii=False)
            
            print(f"\nParsed output saved to: {output_json_path}")
            
            return output_data
            
    except PyPDF2.errors.PdfReadError as e:
        print(f"Error: Failed to read PDF file: {e}")
        return {}
    except Exception as e:
        print(f"Error: An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        return {}


def main():
    """Main function to handle command line arguments"""
    # Default to the PDF in the documents folder
    script_dir = Path(__file__).parent
    default_pdf = script_dir / "documents" / "EDI Remittance Advice Report_2063_20250731-1.pdf"
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = str(default_pdf)
    
    # Optional second argument for custom JSON output path
    output_json_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    parse_pdf(pdf_path, output_json_path)


if __name__ == "__main__":
    main()
