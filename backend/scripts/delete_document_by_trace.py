#!/usr/bin/env python3
"""
Script to delete a specific document from the master-edi Azure AI Search index.

This script allows you to delete a document by providing:
- trace_number: The trace number of the transaction
- amount: The transaction amount (must match exactly)
- effective_date: The effective date in YYYY-MM-DD format

The document will only be deleted if all three values match exactly.

Usage:
    python backend/scripts/delete_document_by_trace.py
    
    Or from the backend directory:
    python scripts/delete_document_by_trace.py
"""

import os
import sys
from pathlib import Path

# Add the backend directory to the path so we can import modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
from azure.azure_search_setup import EDISearchService
import logging

# Load environment variables
load_dotenv(dotenv_path=backend_dir / ".env")
load_dotenv()  # Also load from process environment

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to delete a document by trace number, amount, and effective date"""
    
    print("=" * 60)
    print("Master EDI Azure AI Search - Delete Document by Trace Number")
    print("=" * 60)
    print()
    
    # Verify environment variables
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_API_KEY")
    
    if not endpoint or not api_key:
        print("ERROR: Missing required environment variables!")
        print("Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY")
        print("in your backend/.env file or environment variables.")
        sys.exit(1)
    
    print(f"Endpoint: {endpoint}")
    print(f"Index Name: master-edi")
    print()
    
    # ============================================================
    # PLACEHOLDERS: Edit these values to specify the document to delete
    # ============================================================
    TRACE_NUMBER = "274646"  # Example: "051000013392615"
    AMOUNT = 0       # Example: 7394.46 (must match exactly, including decimal places)
    EFFECTIVE_DATE = "2024-03-06"  # Example: "2025-02-25" (format: YYYY-MM-DD)
    # ============================================================
    
    # Validate inputs
    if not TRACE_NUMBER:
        print("ERROR: TRACE_NUMBER is required!")
        print("Please edit the script and set the TRACE_NUMBER variable.")
        sys.exit(1)
    
    if AMOUNT == 0.0 and TRACE_NUMBER:  # Allow 0.0 if explicitly set
        print("WARNING: AMOUNT is 0.0. Make sure this is correct.")
        response = input("Continue with amount 0.0? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Operation cancelled.")
            sys.exit(0)
    
    if not EFFECTIVE_DATE:
        print("ERROR: EFFECTIVE_DATE is required!")
        print("Please edit the script and set the EFFECTIVE_DATE variable (format: YYYY-MM-DD).")
        sys.exit(1)
    
    # Validate date format
    try:
        from datetime import datetime
        datetime.strptime(EFFECTIVE_DATE, '%Y-%m-%d')
    except ValueError:
        print(f"ERROR: Invalid date format '{EFFECTIVE_DATE}'")
        print("Date must be in YYYY-MM-DD format (e.g., '2025-02-25')")
        sys.exit(1)
    
    # Prepare the trace_numbers dictionary
    # Format: {trace_number: [amount, effective_date]}
    trace_numbers = {
        TRACE_NUMBER: [AMOUNT, EFFECTIVE_DATE]
    }
    
    print("Document to delete:")
    print(f"  Trace Number: {TRACE_NUMBER}")
    print(f"  Amount: {AMOUNT}")
    print(f"  Effective Date: {EFFECTIVE_DATE}")
    print()
    print("WARNING: This will delete the document matching ALL three values!")
    print("The document will only be deleted if trace_number, amount, AND effective_date all match.")
    print()
    
    # Confirm deletion
    response = input("Are you sure you want to delete this document? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("Operation cancelled.")
        sys.exit(0)
    
    print()
    print("Connecting to Azure AI Search...")
    
    try:
        # Initialize the search service
        search_service = EDISearchService(index_name="master-edi")
        
        # Search for the document first to verify it exists
        print("Searching for the document...")
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
        
        search_client = SearchClient(
            endpoint=endpoint,
            index_name="master-edi",
            credential=AzureKeyCredential(api_key)
        )
        
        # Escape single quotes in trace number for the filter
        escaped_trace = TRACE_NUMBER.replace("'", "''")
        filter_expr = f"trace_number eq '{escaped_trace}'"
        search_results = search_client.search(
            search_text="",
            filter=filter_expr,
            top=10
        )
        
        matching_docs = []
        for doc in search_results:
            if (doc.get("amount") == AMOUNT and 
                doc.get("effective_date") == EFFECTIVE_DATE):
                matching_docs.append(doc)
        
        if not matching_docs:
            print()
            print("=" * 60)
            print("⚠ NO MATCHING DOCUMENT FOUND")
            print("=" * 60)
            print("No document found with the exact combination of:")
            print(f"  Trace Number: {TRACE_NUMBER}")
            print(f"  Amount: {AMOUNT}")
            print(f"  Effective Date: {EFFECTIVE_DATE}")
            print()
            print("The document may not exist, or the values may not match exactly.")
            sys.exit(0)
        
        print(f"Found {len(matching_docs)} matching document(s).")
        print()
        
        # Delete the document(s)
        print("Deleting document(s)...")
        result = search_service.delete_documents_by_trace_numbers(trace_numbers)
        
        print()
        print("=" * 60)
        if result["success"]:
            print("✓ SUCCESS")
            print(f"  Deleted: {result.get('deleted_count', 0)} document(s)")
            print(f"  Message: {result['message']}")
        else:
            print("✗ FAILED")
            print(f"  Error: {result.get('error', 'Unknown error')}")
            print(f"  Message: {result['message']}")
            sys.exit(1)
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"Error during document deletion: {e}", exc_info=True)
        print()
        print("=" * 60)
        print("✗ ERROR")
        print(f"  Failed to delete document: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

