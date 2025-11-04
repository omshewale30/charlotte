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
load_dotenv()

class AlignRxSearchService:
    """Service to manage alignRx reports in Azure AI Search"""
    
    def __init__(self):
        """Initialize the AlignRxSearchService"""
        endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        api_key = os.getenv("AZURE_SEARCH_API_KEY")
        index_name = os.getenv("AZURE_ALIGN_RX_SEARCH_INDEX_NAME", "alignrx-reports")

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
        
    def check_if_report_exists(self, pay_date: str, destination: str, payment_amount: float) -> bool:
        """
        Check if a report exists in the search index using exact field matching.
        
        Args:
            pay_date: Date in YYYY-MM-DD format
            destination: Destination string (e.g., "STUDENT STORES PHARMACY")
            payment_amount: Payment amount as float
            
        Returns:
            True if a matching report exists, False otherwise
        """
        try:
            # Convert date string to DateTimeOffset format for filtering
            # pay_date is Edm.DateTimeOffset, so we need ISO 8601 format with timezone
            # Use the full day range to ensure we catch the date regardless of time
            date_start = f"{pay_date}T00:00:00Z"
            date_end = f"{pay_date}T23:59:59Z"
            
            # Build filter expression for exact matching
            # pay_date is DateTimeOffset, destination is string, payment_amount is double
            filter_expr = (
                f"pay_date ge {date_start} and pay_date le {date_end} and "
                f"destination eq '{destination}' and "
                f"payment_amount eq {payment_amount}"
            )
            
            # Use filter parameter for exact matching (not search_text)
            result = self.search_client.search(
                search_text="",  # Empty search text, using filter only
                filter=filter_expr,
                select=["report_id"],  # Only need to know if it exists
                top=1  # Only need to check if at least one exists
            )
            
            # SearchItemPaged is an iterator, so we need to iterate to check existence
            for _ in result:
                return True  # Found at least one match
            return False  # No matches found
        except Exception as e:
            logger.error(f"Error checking if report exists: {e}")
            return False
    
    def clear_all_documents(self) -> Dict:
        """
        Delete all documents from the search index.
        
        Returns:
            Dict with success status and count of deleted documents
        """
        try:
            # Get total count first
            count_result = self.search_client.search(
                search_text="*",
                include_total_count=True,
                top=0
            )
            total_before = count_result.get_count()
            
            if total_before == 0:
                logger.info("Index is already empty")
                return {
                    "success": True,
                    "deleted_count": 0,
                    "message": "Index is already empty"
                }
            
            logger.info(f"Found {total_before} documents to delete")
            
            # Retrieve all document IDs (using report_id as the key field)
            # We'll fetch in batches to avoid memory issues
            all_doc_ids = []
            batch_size = 1000
            
            # Search for all documents, selecting only the key field
            # Note: Azure Search requires the key field name from the schema
            results = self.search_client.search(
                search_text="*",
                select=["report_id"],
                include_total_count=True
            )
            
            # Collect all IDs - Azure Search delete_documents expects documents
            # with the key field matching the schema (report_id in this case)
            for doc in results:
                if "report_id" in doc:
                    all_doc_ids.append({"report_id": doc["report_id"]})
                # Also check for "id" in case documents use that field name
                elif "id" in doc:
                    all_doc_ids.append({"report_id": doc["id"]})
            
            if not all_doc_ids:
                logger.warning("No document IDs found to delete")
                return {
                    "success": True,
                    "deleted_count": 0,
                    "message": "No documents found to delete"
                }
            
            # Delete documents in batches
            total_deleted = 0
            for i in range(0, len(all_doc_ids), batch_size):
                batch = all_doc_ids[i:i + batch_size]
                try:
                    result = self.search_client.delete_documents(documents=batch)
                    successful = sum(1 for r in result if r.succeeded)
                    total_deleted += successful
                    logger.info(f"Deleted batch {i//batch_size + 1}: {successful}/{len(batch)} documents")
                except Exception as batch_error:
                    logger.error(f"Error deleting batch {i//batch_size + 1}: {batch_error}")
            
            logger.info(f"Total documents deleted: {total_deleted}/{len(all_doc_ids)}")
            
            return {
                "success": True,
                "deleted_count": total_deleted,
                "total_before": total_before,
                "message": f"Successfully deleted {total_deleted} documents from index '{self.index_name}'"
            }
            
        except Exception as e:
            logger.error(f"Error clearing index: {e}")
            return {
                "success": False,
                "deleted_count": 0,
                "error": str(e),
                "message": f"Failed to clear index: {e}"
            }

    # def setup_azure_alignRx_search_from_env(self):
    #     """Initialize search service from environment variables.

    #     Loads variables from `backend/.env` so the script works regardless of the
    #     current working directory.
    #     """
    #     # Resolve the backend .env path relative to this file
    #     backend_dir = os.path.dirname(os.path.abspath(__file__))
    #     env_path = os.path.join(backend_dir, ".env")

    #     # Load environment variables from backend/.env if it exists
    #     load_dotenv(dotenv_path=env_path)

    #     # Also load any process-level env vars (without overriding existing)
    #     load_dotenv(override=False)

    #     endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    #     api_key = os.getenv("AZURE_SEARCH_API_KEY")
    #     index_name = os.getenv("AZURE_ALIGN_RX_SEARCH_INDEX_NAME", "alignrx-reports")

    #     if not endpoint or not api_key:
    #         raise ValueError("Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY in backend/.env or environment")

    #     return AlignRxSearchService(endpoint, api_key, index_name=index_name)