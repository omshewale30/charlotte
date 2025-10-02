from azure.cosmos import CosmosClient
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AzureCosmosClient:
    def __init__(self):
        self.client = CosmosClient(os.getenv("AZURE_COSMOS_ENDPOINT"), os.getenv("AZURE_COSMOS_KEY"))
        self.database = self.client.get_database_client(os.getenv("AZURE_COSMOS_DATABASE"))
        self.container = self.database.get_container_client(os.getenv("AZURE_COSMOS_CONTAINER"))
    
    def create_new_session(self, session_id: str, user_id: str, title: str = "New Chat"):
        session = {
            "id": session_id,
            "sessionId": session_id,  # For partition key
            "userId": user_id,
            "user_id": user_id,  # Support both naming conventions
            "title": title,
            "messages": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "type": "Session"
        }
        result = self.container.upsert_item(session)
        return result
    
    
    def get_session(self, session_id: str):
        try:
            return self.container.read_item(item=session_id, partition_key=session_id)
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {str(e)}")
            raise

    def update_session(self, session_id: str, user_id: str, messages: list, title: str = None):
        try:
            # Get existing session to preserve other fields
            existing_session = self.get_session(session_id)

            updated_session = {
                **existing_session,
                "userId": user_id,
                "user_id": user_id,
                "messages": messages,
                "updatedAt": datetime.now().isoformat()
            }

            if title:
                updated_session["title"] = title

            result = self.container.upsert_item(updated_session)
            return result
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {str(e)}")
            raise

    def delete_session(self, session_id: str):
        try:
            self.container.delete_item(item=session_id, partition_key=session_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {str(e)}")
            raise

    def rename_session(self, session_id: str, new_title: str):
        try:
            existing_session = self.get_session(session_id)
            updated_session = {
                **existing_session,
                "title": new_title,
                "updatedAt": datetime.now().isoformat()
            }
            result = self.container.upsert_item(updated_session)
            return result
        except Exception as e:
            logger.error(f"Error renaming session {session_id}: {str(e)}")
            raise
    

    def get_sessions_for_user_id(self, user_id: str):
        try:
            query = "SELECT * FROM c WHERE c.userId = @userId AND c.type = 'Session' ORDER BY c.updatedAt DESC"

            params = [
                {"name": "@userId", "value": user_id}
            ]

            items = self.container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True
            )

            sessions = list(items)
            logger.info(f"Found {len(sessions)} sessions for user {user_id}:")
            for session in sessions:
                logger.info(f"  - {session.get('title', 'Untitled')} (ID: {session['id']})")

            return sessions
        except Exception as e:
            logger.error(f"Error getting sessions for user {user_id}: {str(e)}")
            raise

