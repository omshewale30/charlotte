from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from typing import List, Optional
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import uvicorn

# Load environment variables from .env file
load_dotenv()

# Azure imports
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
from azure.identity import ClientSecretCredential
# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No vector store setup needed for Azure agent
    print("Starting up ...")
    project_client = setup_azure_client()
    app.state.project_client = project_client
    yield
    print("Shutting down ...")
    app.state.project_client.close()

session_threads = {}

# Initialize FastAPI app
app = FastAPI(title="Charlotte",
              description="Charlotte is a chatbot that can answer questions about the UNC Charlotte campus and its resources.",
              version="1.0.0",
              lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define request and response models
class Message(BaseModel):
    role: str
    content: str

class QueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    messages: Optional[List[Message]] = []

class Source(BaseModel):
    document_name: str
    text_snippet: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    conversation_id: str


def setup_azure_client():
    project_endpoint = os.getenv("AZURE_AI_ENDPOINT")
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")

        # Check for missing environment variables
    missing_vars = []
    if not project_endpoint:
        missing_vars.append("AZURE_AI_ENDPOINT")
    if not tenant_id:
        missing_vars.append("AZURE_TENANT_ID")
    if not client_id:
        missing_vars.append("AZURE_CLIENT_ID")
    if not client_secret:
        missing_vars.append("AZURE_CLIENT_SECRET")
    
    if missing_vars:
        error_msg = f"Missing required Azure environment variables: {', '.join(missing_vars)}"
        print(f"ERROR: {error_msg}")
        raise ValueError(error_msg)
    try:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        project_client = AIProjectClient(
            credential=credential,
            endpoint=project_endpoint
        )
        print(f"Azure client setup successfully")
        return project_client
    except Exception as e:
        error_msg = f"Failed to create Azure client: {str(e)}"
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)

def get_agent(project_client):
    """
    Get the agent from the project client
    """
    agent_id = os.getenv("AZURE_AGENT_ID")
    if not agent_id:
        error_msg = "AZURE_AGENT_ID is not set"
        print(f"ERROR: {error_msg}")
        raise ValueError(error_msg)
    try:
        agent = project_client.agents.get_agent(agent_id)
        print(f"Agent {agent_id} retrieved successfully")
        return agent
    except Exception as e:
        error_msg = f"Failed to get agent: {str(e)}"
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)

@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Query the agent
    """
    conversation_id = request.conversation_id

    project_client = app.state.project_client
    agent = get_agent(project_client)
    thread = session_threads.get(conversation_id, None)

    if not thread:
        thread = project_client.agents.threads.create()
        session_threads[conversation_id] = thread
    else:
        thread = project_client.agents.threads.get(thread.id)

    message = project_client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=request.query
    )
    run = project_client.agents.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent.id
    )

    if run.status == "failed":
        print(f"Run failed: {run.error}")
        return {
            "answer": "I'm sorry, I'm having trouble answering your question. Please try again later.",
            "sources": [],
            "conversation_id": thread.id
        }
    else:
        messages = project_client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
        assistant_messages = [msg for msg in messages if msg.role == "assistant"]
        if assistant_messages:
            latest_message = assistant_messages[-1]
            # Extract the text value from the message content
            if latest_message.content and isinstance(latest_message.content, list):
                text_content = ""
                for part in latest_message.content:
                    if part.get("type") == "text" and "text" in part and "value" in part["text"]:
                        text_content = part["text"]["value"]
                        break
                if not text_content:
                    text_content = "I'm sorry, I couldn't find a valid response from the assistant."
            else:
                text_content = "I'm sorry, I couldn't find a valid response from the assistant."
        else:
            text_content = "I'm sorry, I'm having trouble answering your question. Please try again later."

        return {
            "answer": text_content,
            "sources": [],
            "conversation_id": thread.id
        }
    


if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["**/networkx/**"]
    )