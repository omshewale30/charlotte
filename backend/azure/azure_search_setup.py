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
    
    def __init__(self, index_name: str):
        load_dotenv()
        endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        api_key = os.getenv("AZURE_SEARCH_API_KEY")
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
        Check if a file already exists in the search index.
        """
        if not file_name:
            return False
        
        try:
            escaped_file_name = file_name.replace("'", "''")
            filter_expr = f"file_name eq '{escaped_file_name}'"
            result = self.search_client.search(
                search_text="",  # Empty search text, using filter only
                filter=filter_expr,
                top=1  # Only need one match to know at least one exists
            )
            for _ in result:
                return True  # At least one result found
            return False
        except Exception as e:
            logger.error(f"Error checking if file exists: {e}")
            return False
        


    def check_if_trace_numbers_exist(self, trace_numbers: Dict[str, float]) -> bool:
        """
        Check if any trace number from the dictionary already exists in the search index
        AND if the amount for that trace number also matches.

        Args:
            trace_numbers: Dictionary where keys are trace numbers (str) and values are amounts (float)
        Returns:
            True if any trace number exists in the index AND its amount matches, False otherwise
        """
        if not trace_numbers:
            return False

        # Build filter expression using search.in for efficient OR query
        try:
            # Escape single quotes in trace numbers and create comma-separated string
            trace_number_list = [str(tn) for tn in trace_numbers.keys()]
            values_str = ",".join(trace_number_list)
            
            # Use search.in filter: search.in(field, 'value1,value2,value3', ',')
            filter_expr = f"search.in(trace_number, '{values_str}', ',')"
            
            # Search for documents with matching trace numbers
            result = self.search_client.search(
                search_text="",  # Empty search text, using filter only
                filter=filter_expr,
                top=len(trace_numbers)  # Get all potential matches
            )
            
            # Check each result: trace number must exist AND amount must match
            for r in result:
                trace_num = r.get("trace_number")
                indexed_amount = r.get("amount")
                expected_amount = trace_numbers.get(trace_num)
                
                # If trace number exists and amount matches, return True
                if trace_num in trace_numbers and indexed_amount == expected_amount:
                    return True
                
            return False

        except Exception as e:
            logger.error(f"Error checking if trace numbers exist: {e}")
            return False

    def clear_all_documents(self) -> Dict:
        """
        Delete all documents from the search index.
        
        This method retrieves all document IDs from the index and deletes them in batches.
        The key field for EDI transactions is "id".
        
        Returns:
            Dict with success status and count of deleted documents:
            {
                "success": bool,
                "deleted_count": int,
                "total_before": int,
                "message": str,
                "error": str (only if success is False)
            }
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
                logger.info(f"Index '{self.index_name}' is already empty")
                return {
                    "success": True,
                    "deleted_count": 0,
                    "total_before": 0,
                    "message": f"Index '{self.index_name}' is already empty"
                }
            
            logger.info(f"Found {total_before} documents to delete from index '{self.index_name}'")
            
            # Retrieve all document IDs (using "id" as the key field for EDI transactions)
            # We'll fetch in batches to avoid memory issues
            all_doc_ids = []
            batch_size = 1000
            skip = 0
            
            # Search for all documents, selecting only the key field ("id")
            # Azure Search delete_documents expects documents with the key field matching the schema
            while True:
                results = self.search_client.search(
                    search_text="*",
                    select=["id"],  # EDI transactions use "id" as the key field
                    top=batch_size,
                    skip=skip
                )
                
                batch_ids = []
                for doc in results:
                    if "id" in doc:
                        all_doc_ids.append({"id": doc["id"]})
                        batch_ids.append(doc["id"])
                
                if len(batch_ids) < batch_size:
                    break
                skip += batch_size
            
            if not all_doc_ids:
                logger.warning("No document IDs found to delete")
                return {
                    "success": True,
                    "deleted_count": 0,
                    "total_before": total_before,
                    "message": "No documents found to delete"
                }
            
            logger.info(f"Retrieved {len(all_doc_ids)} document IDs for deletion")
            
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
            
            logger.info(f"Total documents deleted: {total_deleted}/{len(all_doc_ids)} from index '{self.index_name}'")
            
            return {
                "success": True,
                "deleted_count": total_deleted,
                "total_before": total_before,
                "message": f"Successfully deleted {total_deleted} documents from index '{self.index_name}'"
            }
            
        except Exception as e:
            logger.error(f"Error clearing index '{self.index_name}': {e}")
            return {
                "success": False,
                "deleted_count": 0,
                "total_before": 0,
                "error": str(e),
                "message": f"Failed to clear index '{self.index_name}': {e}"
            }


