#!/usr/bin/env python3
"""
Script to clear all documents from the AlignRx Azure AI Search index.

This script allows you to delete all indexed data from the search index
to start fresh during testing or maintenance.

Usage:
    python backend/scripts/clear_alignrx_index.py
    
    Or from the backend directory:
    python scripts/clear_alignrx_index.py
"""

import os
import sys
from pathlib import Path

# Add the backend directory to the path so we can import modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
from azure.azure_alignRx_search_setup import AlignRxSearchService
import logging
from azure.azure_search_setup import EDISearchService

# Load environment variables
load_dotenv(dotenv_path=backend_dir / ".env")
load_dotenv()  # Also load from process environment

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to clear the AlignRx search index"""
    
    print("=" * 60)
    print("AlignRx Azure AI Search Index - Clear All Documents")
    print("=" * 60)
    print()
    
    # Verify environment variables
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_API_KEY")
    index_name = os.getenv("master-edi")
    
    if not endpoint or not api_key:
        print("ERROR: Missing required environment variables!")
        print("Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY")
        print("in your backend/.env file or environment variables.")
        sys.exit(1)
    
    print(f"Endpoint: {endpoint}")
    print(f"Index Name: {index_name}")
    print()
    
    # Confirm deletion
    print("WARNING: This will delete ALL documents from the search index!")
    print("This action cannot be undone.")
    print()
    
    response = input("Are you sure you want to continue? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("Operation cancelled.")
        sys.exit(0)
    
    print()
    print("Connecting to Azure AI Search...")
    
    try:
        # Initialize the search service
        search_service = EDISearchService(index_name="master-edi")
        
        # Get statistics before deletion
        stats = search_service.get_statistics()
        if stats:
            print(f"\nCurrent index statistics:")
            print(f"  Total documents: {stats.get('total_transactions', 'N/A')}")
            print(f"  Index name: {stats.get('index_name', 'N/A')}")
            print()
        
        # Clear all documents
        print("Deleting all documents...")
        result = search_service.clear_all_documents()
        
        print()
        print("=" * 60)
        if result["success"]:
            print("✓ SUCCESS")
            print(f"  Deleted: {result.get('deleted_count', 0)} documents")
            if 'total_before' in result:
                print(f"  Total before: {result['total_before']} documents")
            print(f"  Message: {result['message']}")
        else:
            print("✗ FAILED")
            print(f"  Error: {result.get('error', 'Unknown error')}")
            print(f"  Message: {result['message']}")
            sys.exit(1)
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"Error during index clearing: {e}", exc_info=True)
        print()
        print("=" * 60)
        print("✗ ERROR")
        print(f"  Failed to clear index: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

