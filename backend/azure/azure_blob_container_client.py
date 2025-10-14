'''
Azure Blob Container Client
This module provides a client for interacting with Azure Blob Storage containers.
'''

from azure.storage.blob import BlobServiceClient

import os
from dotenv import load_dotenv

load_dotenv()

class AzureBlobContainerClient:
    def __init__(self, connection_string: str, container_name: str):
        self.connection_string = connection_string
        self.container_name = container_name
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_client = self.blob_service_client.get_container_client(container_name)
        # Ensure the container exists
        try:
            if not self.container_client.exists():
                self.blob_service_client.create_container(container_name)
        except Exception:
            # If exists() is not available or raises due to permissions, best-effort get properties
            # This will raise if the container truly does not exist
            self.container_client.get_container_properties()
    
    def list_blobs(self):
        return self.container_client.list_blobs()
    
    def upload_blob(self, blob_name: str, data: bytes, overwrite: bool = True):
        self.container_client.upload_blob(name=blob_name, data=data, overwrite=overwrite)
    
    def download_blob(self, blob_name: str):
        return self.container_client.download_blob(blob_name)

    def download_blob_bytes(self, blob_name: str) -> bytes:
        downloader = self.download_blob(blob_name)
        return downloader.readall()

    def get_container_client(self, container_name: str = None):
        """Return a container client; if name not provided, return the default one."""
        if container_name and container_name != self.container_name:
            return self.blob_service_client.get_container_client(container_name)
        return self.container_client
    
    def get_blob_properties(self, blob_name: str):
        """Get properties of a specific blob"""
        blob_client = self.container_client.get_blob_client(blob_name)
        return blob_client.get_blob_properties()
    
    def get_blob_url(self, blob_name: str):
        """Get the URL for a specific blob"""
        blob_client = self.container_client.get_blob_client(blob_name)
        return blob_client.url


def main():
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
    if not connection_string or not container_name:
        print("Missing AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_CONTAINER_NAME environment variables")
        return

    print("Environment OK: using provided Azure Storage settings.")
    try:
        client = AzureBlobContainerClient(connection_string, container_name)
        print(f"Connected to container '{container_name}'.")
    except Exception as exc:
        print(f"Failed to create container client: {exc}")
        return
    try:
        print(f"Listing blobs in container '{container_name}'...")
        count = 0
        for blob in client.list_blobs():
            print(f"- {blob.name}")
            count += 1
        if count == 0:
            print("No blobs found.")
        else:
            print(f"Total blobs: {count}")
    except Exception as exc:
        print(f"Failed to list blobs: {exc}")

if __name__ == "__main__":
    main()