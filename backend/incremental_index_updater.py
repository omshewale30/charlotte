"""
Incremental Index Updater for EDI Transactions
This module handles tracking processed files and updating the search index with only new files.
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

from azure.azure_blob_container_client import AzureBlobContainerClient
from edi_preprocessor import EDITransactionExtractor
from azure.azure_search_setup import EDISearchService, setup_azure_search_from_env

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProcessedFileInfo:
    """Information about a processed file"""
    filename: str
    last_modified: str
    size: int
    processed_at: str
    transaction_count: int

class IncrementalIndexUpdater:
    """Manages incremental updates to the EDI search index"""

    def __init__(self):
        load_dotenv()

        # Azure configuration
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.source_container = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "edi-reports")
        self.metadata_container = "edi-metadata"  # Container to store processing metadata
        self.metadata_blob_name = "processed_files_registry.json"

        # Initialize clients
        if not self.connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING is required")

        self.source_client = AzureBlobContainerClient(self.connection_string, self.source_container)
        self.metadata_client = AzureBlobContainerClient(self.connection_string, self.metadata_container)

        # Initialize processors
        self.extractor = EDITransactionExtractor()
        self.search_service = None

    def get_search_service(self) -> EDISearchService:
        """Get or initialize the search service"""
        if self.search_service is None:
            self.search_service = setup_azure_search_from_env()
        return self.search_service

    def load_processed_files_registry(self) -> Dict[str, ProcessedFileInfo]:
        """Load the registry of processed files from Azure Blob Storage"""
        try:
            data_bytes = self.metadata_client.download_blob_bytes(self.metadata_blob_name)
            data_text = data_bytes.decode('utf-8')
            registry_data = json.loads(data_text)

            # Convert to ProcessedFileInfo objects
            registry = {}
            for filename, info in registry_data.items():
                registry[filename] = ProcessedFileInfo(
                    filename=info['filename'],
                    last_modified=info['last_modified'],
                    size=info['size'],
                    processed_at=info['processed_at'],
                    transaction_count=info['transaction_count']
                )

            logger.info(f"Loaded registry with {len(registry)} processed files")
            return registry

        except Exception as e:
            logger.info(f"No existing registry found or error loading: {e}")
            return {}

    def save_processed_files_registry(self, registry: Dict[str, ProcessedFileInfo]) -> bool:
        """Save the registry of processed files to Azure Blob Storage"""
        try:
            # Convert ProcessedFileInfo objects to dictionaries
            registry_data = {}
            for filename, info in registry.items():
                registry_data[filename] = {
                    'filename': info.filename,
                    'last_modified': info.last_modified,
                    'size': info.size,
                    'processed_at': info.processed_at,
                    'transaction_count': info.transaction_count
                }

            data_bytes = json.dumps(registry_data, indent=2).encode('utf-8')
            self.metadata_client.upload_blob(self.metadata_blob_name, data_bytes, overwrite=True)

            logger.info(f"Saved registry with {len(registry)} processed files")
            return True

        except Exception as e:
            logger.error(f"Error saving registry: {e}")
            return False

    def get_blob_info(self, blob_name: str) -> Optional[Dict]:
        """Get blob metadata (size, last_modified)"""
        try:
            # Get blob properties
            blob_props = self.source_client.container_client.get_blob_client(blob_name).get_blob_properties()
            return {
                'name': blob_name,
                'size': blob_props.size,
                'last_modified': blob_props.last_modified.isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting blob info for {blob_name}: {e}")
            return None

    def find_new_and_updated_files(self) -> Tuple[List[str], Dict[str, ProcessedFileInfo]]:
        """
        Find files that are new or have been updated since last processing
        Returns: (list_of_new_files, current_registry)
        """
        registry = self.load_processed_files_registry()
        new_files = []

        try:
            # Get all PDF blobs from source container
            current_blobs = {}
            for blob in self.source_client.list_blobs():
                blob_name = getattr(blob, 'name', '')
                if not blob_name.lower().endswith('.pdf'):
                    continue

                blob_info = self.get_blob_info(blob_name)
                if blob_info:
                    current_blobs[blob_name] = blob_info

            logger.info(f"Found {len(current_blobs)} PDF files in source container")

            # Check each blob against registry
            for blob_name, blob_info in current_blobs.items():
                if blob_name not in registry:
                    # New file
                    new_files.append(blob_name)
                    logger.info(f"New file found: {blob_name}")
                else:
                    # Check if file was modified
                    processed_info = registry[blob_name]
                    if (blob_info['last_modified'] != processed_info.last_modified or
                        blob_info['size'] != processed_info.size):
                        new_files.append(blob_name)
                        logger.info(f"Updated file found: {blob_name}")

            logger.info(f"Found {len(new_files)} new or updated files")
            return new_files, registry

        except Exception as e:
            logger.error(f"Error finding new files: {e}")
            return [], registry

    def process_files_incrementally(self, file_list: List[str]) -> Tuple[List[Dict], int]:
        """
        Process only the specified files and extract transactions
        Returns: (transactions, total_count)
        """
        all_transactions = []

        for blob_name in file_list:
            try:
                logger.info(f"Processing: {blob_name}")

                # Download and process the blob
                downloader = self.source_client.download_blob(blob_name)
                pdf_bytes = downloader.readall()

                # Extract text and transactions
                text = self.extractor.extract_text_from_pdf_bytes(pdf_bytes)
                if not text:
                    logger.warning(f"No text extracted from {blob_name}")
                    continue

                pages = self.extractor.split_pages(text)
                file_transactions = []

                for page_text in pages:
                    if 'PAYMENT INFORMATION:' in page_text and 'CREDIT:' in page_text:
                        transaction = self.extractor.parse_page_content(page_text, blob_name)
                        if transaction:
                            file_transactions.append(transaction)

                # Convert to dictionaries
                for transaction in file_transactions:
                    all_transactions.append(transaction.to_dict())

                logger.info(f"Extracted {len(file_transactions)} transactions from {blob_name}")

            except Exception as e:
                logger.error(f"Error processing {blob_name}: {e}")
                continue

        logger.info(f"Total transactions extracted: {len(all_transactions)}")
        return all_transactions, len(all_transactions)

    def update_search_index_incrementally(self, new_transactions: List[Dict]) -> bool:
        """Add new transactions to the existing search index"""
        if not new_transactions:
            logger.info("No new transactions to add to search index")
            return True

        try:
            search_service = self.get_search_service()

            # Get current highest ID from search index to continue numbering
            current_stats = search_service.get_statistics()
            current_count = current_stats.get('total_transactions', 0)

            # Prepare documents for search index
            search_documents = []
            for i, transaction in enumerate(new_transactions, start=current_count + 1):
                doc = {
                    "id": str(i),
                    "trace_number": transaction.get("trace_number", ""),
                    "amount": transaction.get("amount", 0.0),
                    "effective_date": transaction.get("effective_date", ""),
                    "receiver": transaction.get("receiver", ""),
                    "originator": transaction.get("originator", ""),
                    "page_number": transaction.get("page_number", ""),
                    "routing_id_credit": transaction.get("routing_id_credit", ""),
                    "routing_id_debit": transaction.get("routing_id_debit", ""),
                    "company_id_debit": transaction.get("company_id_debit", ""),
                    "mutually_defined": transaction.get("mutually_defined", ""),
                    "file_name": transaction.get("file_name", ""),
                    "searchable_text": f"{transaction.get('amount', 0)} {transaction.get('effective_date', '')} {transaction.get('receiver', '')} {transaction.get('originator', '')} {transaction.get('trace_number', '')}"
                }
                search_documents.append(doc)

            # Upload to search index
            success = search_service.upload_documents(search_documents)

            if success:
                logger.info(f"Successfully added {len(search_documents)} documents to search index")
            else:
                logger.error("Failed to add documents to search index")

            return success

        except Exception as e:
            logger.error(f"Error updating search index: {e}")
            return False

    def update_registry_for_processed_files(self, processed_files: List[str],
                                          transaction_counts: Dict[str, int],
                                          registry: Dict[str, ProcessedFileInfo]) -> Dict[str, ProcessedFileInfo]:
        """Update the registry with newly processed files"""
        current_time = datetime.utcnow().isoformat()

        for blob_name in processed_files:
            blob_info = self.get_blob_info(blob_name)
            if blob_info:
                registry[blob_name] = ProcessedFileInfo(
                    filename=blob_name,
                    last_modified=blob_info['last_modified'],
                    size=blob_info['size'],
                    processed_at=current_time,
                    transaction_count=transaction_counts.get(blob_name, 0)
                )

        return registry

    def perform_incremental_update(self) -> Dict[str, any]:
        """
        Main method to perform incremental search index update
        Returns summary of the update process
        """
        try:
            logger.info("Starting incremental index update...")

            # Find new and updated files
            new_files, registry = self.find_new_and_updated_files()

            if not new_files:
                return {
                    "success": True,
                    "message": "No new files to process",
                    "new_files_count": 0,
                    "transactions_added": 0,
                    "processed_files": []
                }

            # Process new files
            new_transactions, total_transactions = self.process_files_incrementally(new_files)

            # Update search index
            search_success = self.update_search_index_incrementally(new_transactions)

            if search_success:
                # Count transactions per file for registry update
                transaction_counts = {}
                for transaction in new_transactions:
                    file_name = transaction.get('file_name', '')
                    transaction_counts[file_name] = transaction_counts.get(file_name, 0) + 1

                # Update registry
                updated_registry = self.update_registry_for_processed_files(
                    new_files, transaction_counts, registry
                )
                registry_saved = self.save_processed_files_registry(updated_registry)

                return {
                    "success": True,
                    "message": f"Successfully processed {len(new_files)} files and added {total_transactions} transactions",
                    "new_files_count": len(new_files),
                    "transactions_added": total_transactions,
                    "processed_files": new_files,
                    "registry_updated": registry_saved
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to update search index",
                    "new_files_count": len(new_files),
                    "transactions_added": 0,
                    "processed_files": new_files
                }

        except Exception as e:
            logger.error(f"Error in incremental update: {e}")
            return {
                "success": False,
                "message": f"Error during incremental update: {str(e)}",
                "error": str(e)
            }

def main():
    """Test the incremental updater"""
    updater = IncrementalIndexUpdater()
    result = updater.perform_incremental_update()

    print(f"Update Result: {result}")

if __name__ == "__main__":
    main()