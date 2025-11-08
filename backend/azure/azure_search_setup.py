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
    
    def __init__(self):
        load_dotenv()
        endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        api_key = os.getenv("AZURE_SEARCH_API_KEY")
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "edi-transactions")
        self.endpoint = endpoint
        self.api_key = api_key
        self.index_name = index_name
        self.search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(api_key)
        )
        self.index_client = SearchIndexClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
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
    
    def check_if_file_exists(self, file_name: str) -> bool:
        """
        Check if transactions from a file already exist in the search index.
        
        Args:
            file_name: The filename to check for
            
        Returns:
            True if transactions from this file exist, False otherwise
        """
        try:
            # Search for any transactions with this file_name
            # Escape single quotes in file_name for the filter
            escaped_file_name = file_name.replace("'", "''")
            filter_expr = f"file_name eq '{escaped_file_name}'"
            
            result = self.search_client.search(
                search_text="",  # Empty search text, using filter only
                filter=filter_expr,
                select=["id"],  # Only need to know if it exists
                top=1  # Only need to check if at least one exists
            )
            
            # SearchItemPaged is an iterator, so we need to iterate to check existence
            for _ in result:
                return True  # Found at least one match
            return False  # No matches found
        except Exception as e:
            logger.error(f"Error checking if file exists: {e}")
            return False


