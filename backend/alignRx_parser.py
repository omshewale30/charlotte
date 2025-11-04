'''
This script is used to parse alignRx excel files and extract the data into a structured format and save it to a database.

'''
import uuid
import os
import glob
import json
import re
import pandas as pd
import sys
from azure.azure_blob_container_client import AzureBlobContainerClient
import datetime
from azure.azure_alignRx_search_setup import AlignRxSearchService

class DuplicateReportError(Exception):
    """Exception raised when a report already exists in the search index"""
    pass

class AlignRxParser:
    def __init__(self):
        self.search_service = AlignRxSearchService()
        
        self.azure_client = AzureBlobContainerClient(connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"), container_name='alignrx-reports')

        


    def parse_excel_report(self, file_path: str) -> dict:
        """
        Parses a single Excel remittance report.

        Args:
            file_path (str): The path to the .xls or .xlsx file.

        Returns:
            dict: A dictionary containing the extracted data, or None if parsing fails.
        """
        try:
            # Read 'Sheet1' without a header.
            # We let pandas auto-detect the engine (xlrd for .xls, openpyxl for .xlsx)

            df = pd.read_excel(file_path, sheet_name='Sheet1', header=None, engine=None)
        except Exception as e:
            print(f"Error reading {file_path}: {e}", file=sys.stderr)
            return None

        report_data = {
            "source_file": os.path.basename(file_path),
            "date": None,
            "destination": None,
            "central_payments": [],
            "processing_fee": None,
            "payment_amount": None
        }
        report_data['id'] = str(uuid.uuid4())
        # We use a state machine to move through the document sections
        # SCANNING -> FIND_CENTRAL_PAY -> PARSE_CENTRAL_PAY -> FIND_TOTAL -> DONE
        state = 'SCANNING'
        
        # Regex to extract sender and check number
        # Matches: "Sender Name (Check # - 12345)"
        payment_line_re = re.compile(r'^(.*?) \(Check # - (.*?)\)')
        
        # Iterate over all rows in the dataframe
        for row in df.itertuples(index=False, name=None):
            # Clean the row: convert all cells to string, strip whitespace,
            # and remove any empty cells resulting from NaNs or empty strings.
            row_cells = [str(cell).strip() for cell in row if pd.notna(cell) and str(cell).strip()]
            
            # Skip fully empty rows
            if not row_cells:
                continue
                
            # Join all cell content for easier searching of keywords
            row_str = " | ".join(row_cells)

            if state == 'SCANNING':
                # Look for the header row with Date and Destination
                if "Pay Date:" in row_str and ("CAMPUS HEALTH PHARMACY" in row_str or "STUDENT STORES PHARMACY" in row_str):
                    for cell in row_cells:
                        if cell.startswith("Pay Date:"):
                            try:
                                raw_date_str = cell.replace("Pay Date:", "").strip()
                                # Parse the date from "MM/DD/YYYY" format
                                date_obj = datetime.datetime.strptime(raw_date_str, '%m/%d/%Y').date()
                                # Format it to "YYYY-MM-DD" string
                                report_data['date'] = date_obj.isoformat()
                            except Exception as e:
                                print(f"Warning: Could not parse date {raw_date_str}. Error: {e}")
                                report_data['date'] = None

                        if "CAMPUS HEALTH PHARMACY" in cell:
                            report_data['destination'] = "CAMPUS HEALTH PHARMACY"
                        elif "STUDENT STORES PHARMACY" in cell:
                            report_data['destination'] = "STUDENT STORES PHARMACY"
                    
                    # If we found both, move to the next state
                    if report_data['date'] and report_data['destination']:
                        state = 'FIND_CENTRAL_PAY'

            elif state == 'FIND_CENTRAL_PAY':
                # Look for the start of the "Central Pay" section
                if "Central Pay" in row_str:
                    state = 'PARSE_CENTRAL_PAY'
                    
            elif state == 'PARSE_CENTRAL_PAY':
                # Now we're in the central pay section, parsing line items
                # until we hit the "Processing Fee"
                
                first_cell = row_cells[0]
                last_cell = row_cells[-1]

                # Check if this row is a payment line
                match = payment_line_re.search(first_cell)
                
                if match:
                    try:
                        # This is a payment line
                        amount = float(last_cell.replace(',', ''))
                        sender = match.group(1).strip()
                        check_num = match.group(2).strip()
                        
                        report_data['central_payments'].append({
                            "sender": sender,
                            "check_num": check_num,
                            "amount": amount
                        })
                    except ValueError:
                        # Failed to parse amount, log and skip line
                        print(f"Warning: Could not parse amount '{last_cell}' for '{first_cell}' in {file_path}", file=sys.stderr)
                    except Exception as e:
                        print(f"Warning: Error parsing line '{row_str}' in {file_path}: {e}", file=sys.stderr)

                # Check if this is the "Processing Fee" line
                elif "Processing Fee" in first_cell:
                    try:
                        fee_amount = float(last_cell.replace(',', ''))
                        report_data['processing_fee'] = fee_amount
                        state = 'FIND_TOTAL' # Move to next state
                    except ValueError:
                        print(f"Warning: Could not parse processing fee amount '{last_cell}' in {file_path}", file=sys.stderr)
                        state = 'FIND_TOTAL' # Still move on

            elif state == 'FIND_TOTAL':
                # Look for the final "Payment Amount" line
                first_cell = row_cells[0]
                last_cell = row_cells[-1]

                if "Payment Amount" in first_cell:
                    try:
                        total_amount = float(last_cell.replace(',', ''))
                        report_data['payment_amount'] = total_amount
                        state = 'DONE'
                        break # We found everything, exit loop
                    except ValueError:
                        print(f"Warning: Could not parse payment amount '{last_cell}' in {file_path}", file=sys.stderr)
                        state = 'DONE'
                        break # Exit loop even if parse failed

        if state != 'DONE':
            print(f"Warning: Parser finished for {file_path} but may be incomplete. Final state: {state}", file=sys.stderr)
        
        required_fields = ['date', 'destination', 'payment_amount']
        missing_fields = [field for field in required_fields if not report_data.get(field)]

        if missing_fields:
            error_msg = f"Parsing incomplete: missing required fields: {', '.join(missing_fields)}. " \
                        f"Report may not match expected schema. Final state: {state}"
            print(f"Error: {error_msg}", file=sys.stderr)
            raise ValueError(error_msg)
        # Check if the report_data is already in the search index
        # We need to check the pay_date, destination, and the total payment amount
        try:
            if self.search_service.check_if_report_exists(
                report_data.get('date'), 
                report_data.get('destination'), 
                report_data.get('payment_amount')
            ):
                print(f"Report {file_path} already exists in the search index", file=sys.stderr)
                raise DuplicateReportError(
                    f"Report with date '{report_data.get('date')}', "
                    f"destination '{report_data.get('destination')}', and "
                    f"payment amount '{report_data.get('payment_amount')}' already exists in the search index"
                )
        except DuplicateReportError:
            # Re-raise duplicate errors so they can be handled by the caller
            raise
        except Exception as e:
            # Log the error but continue processing - if the check fails, 
            # we'll allow the upload to proceed (fail open)
            print(f"Warning: Could not check if report exists in search index: {e}. Continuing with upload.", file=sys.stderr)

        return report_data
    
    def parse_all_reports(self):
        """
        Parses all reports in the AlignRx reports Azure Blob Storage container.
        """
        report_files = self.azure_client.list_blobs(container_name='alignrx-reports', prefix='')
        for file_path in report_files:
            print(f"Processing {file_path}...")
            data = self.parse_excel_report(file_path.name)

    def main():
        """
        Main function to find reports, parse them, and save the aggregated data.
        """
        # Directory where your .xls/.xlsx files are stored
        REPORTS_DIR = 'reports'
        OUTPUT_FILE = 'remittance_summary.json'
        
        # Ensure the reports directory exists
        if not os.path.isdir(REPORTS_DIR):
            print(f"Error: Directory '{REPORTS_DIR}' not found.", file=sys.stderr)
            print("Please create a 'reports' folder and place your Excel files inside it.", file=sys.stderr)
            return

        # Find all Excel files (xls, xlsx) in the directory
        # The 'xls*' glob pattern catches .xls, .xlsx, .xlsm, etc.
        report_files = glob.glob(os.path.join(REPORTS_DIR, '*.xls*'))
        
        if not report_files:
            print(f"No Excel files found in '{REPORTS_DIR}'.", file=sys.stderr)
            return

        print(f"Found {len(report_files)} Excel files to process...")

        all_reports_data = []
        
        for file_path in report_files:
            print(f"Processing {file_path}...")
            data = parse_excel_report(file_path)
            if data:
                all_reports_data.append(data)
                
        # Write the aggregated data to a JSON file
        try:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_reports_data, f, indent=4)
            
            print(f"\nSuccess! All data has been extracted and saved to {OUTPUT_FILE}")
            
        except Exception as e:
            print(f"\nError writing to JSON file {OUTPUT_FILE}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
