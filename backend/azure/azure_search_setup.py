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
from azure.core.exceptions import ResourceNotFoundError
import logging
from azure.azure_blob_container_client import AzureBlobContainerClient

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
            # If index already exists, skip creation
            try:
                existing = self.index_client.get_index(self.index_name)
                if existing:
                    logger.info(f"Index '{self.index_name}' already exists. Skipping creation.")
                    return True
            except ResourceNotFoundError:
                # Not found; proceed to create
                pass

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

    def upload_documents(self, documents: List[Dict]) -> bool:
        """Upload already-shaped documents to the search index."""
        if not documents:
            logger.warning("No documents provided for upload")
            return False

        try:
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
            logger.error(f"Error uploading documents: {e}")
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
    """Initialize search service from environment variables.

    Loads variables from `backend/.env` so the script works regardless of the
    current working directory.
    """
    # Resolve the backend .env path relative to this file
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(backend_dir, ".env")

    # Load environment variables from backend/.env if it exists
    load_dotenv(dotenv_path=env_path)

    # Also load any process-level env vars (without overriding existing)
    load_dotenv(override=False)

    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_API_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "edi-transactions")

    if not endpoint or not api_key:
        raise ValueError("Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY in backend/.env or environment")

    return EDISearchService(endpoint, api_key, index_name=index_name)


def load_latest_transactions_from_blob() -> Optional[List[Dict]]:
    """Download and return the latest transactions JSON from Azure Blob Storage.

    Expects env vars:
    - AZURE_STORAGE_CONNECTION_STRING
    - EDI_JSON_OUTPUT_CONTAINER (defaults to 'edi-json-structured')
    """
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("EDI_JSON_OUTPUT_CONTAINER", "edi-json-structured")

    if not connection_string:
        logger.error("AZURE_STORAGE_CONNECTION_STRING is not set")
        return None

    try:
        client = AzureBlobContainerClient(connection_string, container_name)
        latest_blob = None
        latest_ts = None
        for blob in client.list_blobs():
            name = getattr(blob, 'name', '')
            if not name.lower().endswith('.json'):
                continue
            ts = getattr(blob, 'last_modified', None)
            if latest_ts is None or (ts and ts > latest_ts):
                latest_ts = ts
                latest_blob = name

        if not latest_blob:
            logger.warning(f"No JSON blobs found in container '{container_name}'")
            return None

        logger.info(f"Downloading latest JSON blob: {latest_blob}")
        data_bytes = client.download_blob_bytes(latest_blob)
        data_text = data_bytes.decode('utf-8')
        data = json.loads(data_text)
        return data
    except Exception as e:
        logger.error(f"Failed to load JSON from Azure Blob: {e}")
        return None


def transactions_to_search_documents(transactions: List[Dict]) -> Dict:
    """Transform raw transactions array into Azure Search document schema."""
    search_documents: List[Dict] = []
    for i, t in enumerate(transactions, 1):
        doc = {
            "id": str(i),
            "trace_number": t.get("trace_number", ""),
            "amount": t.get("amount", 0.0),
            "effective_date": t.get("effective_date", ""),
            "receiver": t.get("receiver", ""),
            "originator": t.get("originator", ""),
            "page_number": t.get("page_number"),
            "routing_id_credit": t.get("routing_id_credit", ""),
            "routing_id_debit": t.get("routing_id_debit", ""),
            "company_id_debit": t.get("company_id_debit", ""),
            "mutually_defined": t.get("mutually_defined", ""),
            "file_name": t.get("file_name", ""),
            "searchable_text": f"{t.get('amount', 0)} {t.get('effective_date', '')} {t.get('receiver', '')} {t.get('originator', '')} {t.get('trace_number', '')}"
        }
        search_documents.append(doc)
    return {"documents": search_documents, "total_count": len(search_documents)}

def main():
    """Main setup function using Azure Blob JSON as source"""
    print("Setting up Azure AI Search for EDI transactions...")

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

    print("Creating search index...")
    if search_service.create_index():
        print("✅ Index created successfully")
    else:
        print("❌ Failed to create index")
        return

    # Load latest transactions JSON from Azure Blob
    transactions = load_latest_transactions_from_blob()
    if transactions is None:
        print("❌ No transactions JSON available in Azure Blob.")
        return

    # The blob likely contains raw transactions (array). Transform.
    if isinstance(transactions, dict) and 'documents' in transactions:
        documents = transactions['documents']
    elif isinstance(transactions, list):
        shaped = transactions_to_search_documents(transactions)
        documents = shaped['documents']
    else:
        print("❌ Unexpected JSON format in blob. Expected array of transactions or {documents: [...]}.")
        return

    print(f"Uploading {len(documents)} documents from Azure Blob...")
    if search_service.upload_documents(documents):
        print("✅ Data uploaded successfully")
    else:
        print("❌ Failed to upload data")
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