"""
Azure AI Search integration for EDI transactions
This script sets up the search index and uploads your processed data
"""

import os
from typing import List, Dict
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
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