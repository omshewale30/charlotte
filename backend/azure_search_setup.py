"""
Azure AI Search integration for EDI transactions
This script sets up the search index and uploads your processed data
"""

import json
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SearchableField,
    SimpleField,
    ComplexField
)
from azure.core.credentials import AzureKeyCredential
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EDISearchService:
    """Service to manage EDI transactions in Azure AI Search"""
    
    def __init__(self, endpoint: str, api_key: str, index_name: str = "edi-transactions"):
        self.endpoint = endpoint
        self.api_key = api_key
        self.index_name = index_name
        self.credential = AzureKeyCredential(api_key)
        
        # Initialize clients
        self.index_client = SearchIndexClient(
            endpoint=endpoint,
            credential=self.credential
        )
        self.search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=self.credential
        )
    
    def create_index(self) -> bool:
        """Create the search index with optimized fields for EDI data"""
        try:
            # Define the index schema
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                
                # Transaction identifiers
                SearchableField(name="trace_number", type=SearchFieldDataType.String, 
                              filterable=True, sortable=True),
                SimpleField(name="amount", type=SearchFieldDataType.Double, 
                           filterable=True, sortable=True),
                SimpleField(name="effective_date", type=SearchFieldDataType.String, 
                           filterable=True, sortable=True),
                
                # Party information
                SearchableField(name="receiver", type=SearchFieldDataType.String, 
                              filterable=True),
                SearchableField(name="originator", type=SearchFieldDataType.String, 
                              filterable=True),
                
                # Technical details
                SimpleField(name="page_number", type=SearchFieldDataType.String, 
                           filterable=True),
                SimpleField(name="routing_id_credit", type=SearchFieldDataType.String, 
                           filterable=True),
                SimpleField(name="routing_id_debit", type=SearchFieldDataType.String, 
                           filterable=True),
                SimpleField(name="company_id_debit", type=SearchFieldDataType.String, 
                           filterable=True),
                SimpleField(name="mutually_defined", type=SearchFieldDataType.String, 
                           filterable=True),
                SimpleField(name="file_name", type=SearchFieldDataType.String, 
                           filterable=True),
                
                # Combined searchable text for free-text queries
                SearchableField(name="searchable_text", type=SearchFieldDataType.String, 
                              analyzer_name="en.microsoft")
            ]
            
            # Create the index
            index = SearchIndex(name=self.index_name, fields=fields)
            result = self.index_client.create_index(index)
            
            logger.info(f"Created search index: {self.index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            return False
    
    def upload_transactions(self, json_file_path: str) -> bool:
        """Upload transactions from JSON file to search index"""
        try:
            # Load the processed data
            with open(json_file_path, 'r') as f:
                data = json.load(f)
            
            documents = data.get('documents', [])
            
            if not documents:
                logger.warning("No documents found in JSON file")
                return False
            
            # Upload documents in batches (Azure Search has limits)
            batch_size = 1000
            total_uploaded = 0
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                
                try:
                    result = self.search_client.upload_documents(documents=batch)
                    successful = sum(1 for r in result if r.succeeded)
                    total_uploaded += successful
                    
                    logger.info(f"Uploaded batch {i//batch_size + 1}: {successful}/{len(batch)} documents")
                    
                except Exception as batch_error:
                    logger.error(f"Error uploading batch {i//batch_size + 1}: {batch_error}")
            
            logger.info(f"Total documents uploaded: {total_uploaded}/{len(documents)}")
            return total_uploaded > 0
            
        except Exception as e:
            logger.error(f"Error uploading transactions: {e}")
            return False
    
    def search_by_amount_and_date(self, amount: float, date: str) -> List[Dict]:
        """Search for transactions by exact amount and date"""
        try:
            filter_expr = f"amount eq {amount} and effective_date eq '{date}'"
            
            results = self.search_client.search(
                search_text="",
                filter=filter_expr,
                select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                top=10
            )
            
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"Error searching by amount and date: {e}")
            return []
    
    def search_by_trace_number(self, trace_number: str) -> List[Dict]:
        """Search for transaction by trace number"""
        try:
            filter_expr = f"trace_number eq '{trace_number}'"
            
            results = self.search_client.search(
                search_text="",
                filter=filter_expr,
                select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                top=1
            )
            
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"Error searching by trace number: {e}")
            return []
    
    def search_by_originator(self, originator: str) -> List[Dict]:
        """Search for transactions by originator"""
        try:
            results = self.search_client.search(
                search_text=originator,
                search_fields=["originator"],
                select=["trace_number", "amount", "effective_date", "originator", "receiver"],
                top=50
            )
            
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"Error searching by originator: {e}")
            return []
    
    def free_text_search(self, query: str) -> List[Dict]:
        """Perform free-text search across all searchable fields"""
        try:
            results = self.search_client.search(
                search_text=query,
                search_fields=["searchable_text", "originator", "receiver"],
                select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                top=20
            )
            
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"Error in free text search: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """Get basic statistics about the indexed data"""
        try:
            # Get total count
            count_result = self.search_client.search(
                search_text="*",
                include_total_count=True,
                top=0
            )
            
            total_count = count_result.get_count()
            
            # Get date range
            earliest = self.search_client.search(
                search_text="*",
                order_by=["effective_date asc"],
                select=["effective_date"],
                top=1
            )
            
            latest = self.search_client.search(
                search_text="*",
                order_by=["effective_date desc"],
                select=["effective_date"],
                top=1
            )
            
            earliest_date = None
            latest_date = None
            
            for result in earliest:
                earliest_date = result["effective_date"]
                break
                
            for result in latest:
                latest_date = result["effective_date"]
                break
            
            return {
                "total_transactions": total_count,
                "earliest_date": earliest_date,
                "latest_date": latest_date,
                "index_name": self.index_name
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

def setup_azure_search_from_env():
    """Initialize search service from environment variables"""
    # Load environment variables from .env file
    load_dotenv()
    
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_API_KEY")
    
    if not endpoint or not api_key:
        raise ValueError("Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY environment variables")
    
    return EDISearchService(endpoint, api_key)

def main():
    """Main setup function"""
    print("Setting up Azure AI Search for EDI transactions...")
    
    # You'll need to set these environment variables
    # Or replace with your actual values
    try:
        search_service = setup_azure_search_from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nTo set up Azure AI Search:")
        print("1. Create an Azure AI Search service in Azure Portal")
        print("2. Get the endpoint URL and admin API key")
        print("3. Set environment variables:")
        print("   export AZURE_SEARCH_ENDPOINT='https://your-service.search.windows.net'")
        print("   export AZURE_SEARCH_API_KEY='your-api-key'")
        return
    
    # Create the index
    print("Creating search index...")
    if search_service.create_index():
        print("✅ Index created successfully")
    else:
        print("❌ Failed to create index")
        return
    
    # Upload data
    json_file = "./processed_data/search_index_data.json"
    if os.path.exists(json_file):
        print(f"Uploading data from {json_file}...")
        if search_service.upload_transactions(json_file):
            print("✅ Data uploaded successfully")
        else:
            print("❌ Failed to upload data")
            return
    else:
        print(f"❌ Data file not found: {json_file}")
        print("Please run the EDI preprocessor first to generate the data file")
        return
    
    # Test some queries
    print("\nTesting queries...")
    
    # Test exact search
    results = search_service.search_by_amount_and_date(103.12, "2025-06-02")
    if results:
        print(f"✅ Found transaction: Trace number {results[0].get('trace_number')}")
    else:
        print("❌ No results for test query")
    
    # Get statistics
    stats = search_service.get_statistics()
    if stats:
        print(f"\n📊 Index Statistics:")
        print(f"   Total transactions: {stats.get('total_transactions')}")
        print(f"   Date range: {stats.get('earliest_date')} to {stats.get('latest_date')}")
    
    print("\n🎉 Setup completed! Your EDI search service is ready.")

if __name__ == "__main__":
    main()