#!/usr/bin/env python3
"""
Script to create or update the master-edi Azure AI Search index.

This script creates a new search index named "master-edi" with additional fields
beyond the edi-transactions index, including:
- input_format: The EDI input format (ACHCCD+, ACHCTX, etc.)
- demand_account_credit: The demand account credit field
- line_items: A collection of complex objects containing line item details
  (line_number, seller_invoice_num, invoice_amount, net_amount_paid)

IMPORTANT: Azure Search does not support adding fields to an existing index.
If the index already exists, you must delete and recreate it, which will
require re-indexing all documents.

Usage:
    python backend/scripts/create_master_edi_index.py
    
    Or from the backend directory:
    python scripts/create_master_edi_index.py
"""

import os
import sys
from pathlib import Path

# Add the backend directory to the path so we can import modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    ComplexField,
    SearchFieldDataType
)
from azure.core.credentials import AzureKeyCredential
import logging

# Load environment variables
load_dotenv(dotenv_path=backend_dir / ".env")
load_dotenv()  # Also load from process environment

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_master_edi_index():
    """Create the master-edi Azure AI Search index"""
    
    print("=" * 60)
    print("Azure AI Search - Create master-edi Index")
    print("=" * 60)
    print()
    
    # Verify environment variables
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_API_KEY")
    index_name = "master-edi"
    
    if not endpoint or not api_key:
        print("ERROR: Missing required environment variables!")
        print("Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY")
        print("in your backend/.env file or environment variables.")
        sys.exit(1)
    
    print(f"Endpoint: {endpoint}")
    print(f"Index Name: {index_name}")
    print()
    
    try:
        # Initialize the search index client
        credential = AzureKeyCredential(api_key)
        index_client = SearchIndexClient(
            endpoint=endpoint,
            credential=credential
        )
        
        # Check if index already exists
        try:
            existing_index = index_client.get_index(index_name)
            print(f"WARNING: Index '{index_name}' already exists!")
            print(f"  Fields: {len(existing_index.fields)}")
            response = input("Do you want to delete and recreate it? (yes/no): ").strip().lower()
            
            if response in ['yes', 'y']:
                print(f"Deleting existing index '{index_name}'...")
                index_client.delete_index(index_name)
                print("Index deleted successfully.")
            else:
                print("Operation cancelled.")
                sys.exit(0)
        except Exception:
            # Index doesn't exist, which is fine
            pass
        
        print()
        print("Creating index schema...")
        
        # Define the index fields based on edi-transactions schema
        fields = [
            # Key field
            SimpleField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                searchable=False,
                filterable=False,
                retrievable=True,
                sortable=False,
                facetable=False
            ),
            # Trace number
            SearchableField(
                name="trace_number",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True,
                facetable=False,
                retrievable=True
            ),
            # Amount (numeric)
            SimpleField(
                name="amount",
                type=SearchFieldDataType.Double,
                searchable=False,
                filterable=True,
                sortable=True,
                facetable=True,
                retrievable=True
            ),
            # Effective date (string format YYYY-MM-DD)
            SearchableField(
                name="effective_date",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True,
                facetable=True,
                retrievable=True
            ),
            # Receiver
            SearchableField(
                name="receiver",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True,
                facetable=True,
                retrievable=True
            ),
            # Originator
            SearchableField(
                name="originator",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True,
                facetable=True,
                retrievable=True
            ),
            # Page number
            SimpleField(
                name="page_number",
                type=SearchFieldDataType.String,
                searchable=False,
                filterable=True,
                sortable=True,
                facetable=False,
                retrievable=True
            ),
            # Routing ID Credit
            SimpleField(
                name="routing_id_credit",
                type=SearchFieldDataType.String,
                searchable=False,
                filterable=True,
                sortable=True,
                facetable=False,
                retrievable=True
            ),
            # Routing ID Debit
            SimpleField(
                name="routing_id_debit",
                type=SearchFieldDataType.String,
                searchable=False,
                filterable=True,
                sortable=True,
                facetable=False,
                retrievable=True
            ),
            # Company ID Debit
            SimpleField(
                name="company_id_debit",
                type=SearchFieldDataType.String,
                searchable=False,
                filterable=True,
                sortable=True,
                facetable=False,
                retrievable=True
            ),
            # Mutually defined
            SimpleField(
                name="mutually_defined",
                type=SearchFieldDataType.String,
                searchable=False,
                filterable=True,
                sortable=True,
                facetable=False,
                retrievable=True
            ),
            # File name
            SearchableField(
                name="file_name",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True,
                facetable=False,
                retrievable=True
            ),
            # Searchable text (combined field for full-text search)
            SearchableField(
                name="searchable_text",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=False,
                sortable=False,
                facetable=False,
                retrievable=True
            ),
            # Input format (ACHCCD+, ACHCTX, etc.)
            SimpleField(
                name="input_format",
                type=SearchFieldDataType.String,
                searchable=False,
                filterable=True,
                sortable=True,
                facetable=True,
                retrievable=True
            ),
            # Demand account credit
            SimpleField(
                name="demand_account_credit",
                type=SearchFieldDataType.String,
                searchable=False,
                filterable=True,
                sortable=True,
                facetable=False,
                retrievable=True
            ),
            # Line items (complex field for ACHCTX format details)
            # Note: Fields within collections cannot be sortable in Azure Search
            ComplexField(
                name="line_items",
                fields=[
                    SimpleField(
                        name="line_number",
                        type=SearchFieldDataType.String,
                        searchable=False,
                        filterable=True,
                        sortable=False,  # Cannot be sortable in a collection
                        facetable=False,
                        retrievable=True
                    ),
                    SearchableField(
                        name="seller_invoice_num",
                        type=SearchFieldDataType.String,
                        searchable=True,
                        filterable=True,
                        sortable=False,
                        facetable=False,
                        retrievable=True
                    ),
                    SimpleField(
                        name="invoice_amount",
                        type=SearchFieldDataType.Double,
                        searchable=False,
                        filterable=True,
                        sortable=False,  # Cannot be sortable in a collection
                        facetable=True,
                        retrievable=True
                    ),
                    SimpleField(
                        name="net_amount_paid",
                        type=SearchFieldDataType.Double,
                        searchable=False,
                        filterable=True,
                        sortable=False,  # Cannot be sortable in a collection
                        facetable=True,
                        retrievable=True
                    ),
                ],
                collection=True  # This makes it an array of complex objects
            ),
        ]
        
        # Create the index
        index = SearchIndex(
            name=index_name,
            fields=fields
        )
        
        print(f"Creating index '{index_name}' with {len(fields)} fields...")
        created_index = index_client.create_index(index)
        
        print()
        print("=" * 60)
        print("✓ SUCCESS")
        print(f"  Index '{index_name}' created successfully!")
        print(f"  Fields: {len(created_index.fields)}")
        print("=" * 60)
        print()
        print("Index fields:")
        for field in created_index.fields:
            print(f"  - {field.name} ({field.type})")
        
    except Exception as e:
        logger.error(f"Error creating index: {e}", exc_info=True)
        print()
        print("=" * 60)
        print("✗ ERROR")
        print(f"  Failed to create index: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    create_master_edi_index()

