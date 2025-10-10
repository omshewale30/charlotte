from fastapi import FastAPI, HTTPException, Depends, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from typing import List, Optional, Dict
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import uvicorn
import re
from datetime import datetime
from openai import AzureOpenAI
import json
from auth import get_current_user, require_unc_email, get_optional_user
from edi_preprocessor import EDIProcessor
from azure.azure_blob_container_client import AzureBlobContainerClient
from incremental_index_updater import IncrementalIndexUpdater
from azure.azure_client import AzureClient
from edi_search_integration import EDISearchIntegration
from json_to_excel import EDIDataLoader

# Load environment variables from .env file
load_dotenv()

# Initialize Azure OpenAI client for query triaging
azure_openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
    azure_endpoint=os.getenv("AZURE_AI_RESOURCE_ENDPOINT")
)

async def triage_query(query: str) -> str:
    """
    Use AI to determine if a query should be routed to EDI agent or general AI agent.
    Returns 'edi' or 'general'
    """
    try:
        system_prompt = """You are a query router. Analyze the user's query and determine if it should be routed to:
        1. 'edi' - for queries about EDI transactions, payments, trace numbers, amounts, dates, specific companies like BCBS, transaction searches
        2. 'general' - for all other queries (Campus health procedures, code, etc.)

        Examples of EDI queries:
        - "find all transactions from BCBS of NC in August 2025"
        - "do you have any August 2025 transactions in the db?"
        - "Give me all transactions for the amount of 1761.96 in August 2025"
        - "show me trace number 123456"
        - "what payments were made in June?"

        Examples of general procedure queries:
        - "what is charge code for Campus health Pharmacy?"
        - "Creating CashPro deposits?"
        - "What is the process for creating a claim in ecW?
        - "Any questions about posting a check?"

        Respond with only 'edi' or 'general'."""

        response = azure_openai_client.chat.completions.create(
            model=os.getenv("SMALL_MODEL_NAME", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            max_tokens=10,
            temperature=0.1
        )

        result = response.choices[0].message.content.strip().lower()
        return "edi" if result == "edi" else "general"

    except Exception as e:
        logger.error(f"Error in query triaging: {str(e)}")
        # Fallback to keyword-based routing if AI fails
        edi_keywords = ['trace number', 'transaction', '$', 'amount', 'june', 'august', 'bcbs', 'payment', 'edi']
        if any(keyword in query.lower() for keyword in edi_keywords):
            return "edi"
        return "general"

# Azure imports
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
from azure.identity import ClientSecretCredential
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from conversation_memory import UnifiedConversationMemory
from conversation_memory import ConversationMemory
from azure.azure_cosmos_client import AzureCosmosClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
# Load environment variables from .env file
load_dotenv()

# Define request and response models
class Message(BaseModel):
    role: str
    content: str

class QueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    messages: Optional[List[Message]] = None
    mode: Optional[str] = None

class Source(BaseModel):
    document_name: str
    text_snippet: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    conversation_id: str

# EDI-specific models
class EDIQuery(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    messages: Optional[List[Message]] = None


class TransactionResult(BaseModel):
    trace_number: str
    amount: float
    effective_date: str
    originator: str
    receiver: str
    page_number: Optional[str] = None

class EDIResponse(BaseModel):
    answer: str
    transactions: List[TransactionResult]
    query_type: str
    search_performed: bool


class EDIAnalysisRequest(BaseModel):
    start: str  # YYYY-MM-DD
    end: str    # YYYY-MM-DD


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - initializes clients once on startup"""
    print("Starting up Charlotte...")
    
    # Initialize Azure clients (done once on startup)
    azure_client = AzureClient()
    project_client = azure_client.project_client
    agent = azure_client.agent
    
    # Store clients in app state for global access
    app.state.project_client = project_client
    app.state.agent = agent
    app.state.azure_client = azure_client  # Store the full client for other services
    
    # Initialize conversation memory services

    
    print("Charlotte startup complete!")
    yield
    print("Shutting down Charlotte...")


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


unified_memory = UnifiedConversationMemory()
conversation_memory = ConversationMemory(unified_memory)
edi_search = EDISearchIntegration(unified_memory, conversation_memory)
cosmos_client = AzureCosmosClient()

# Protected Routes
@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest, user: Dict = Depends(require_unc_email)):
    """Azure AI Foundry agent query endpoint with unified memory management"""
    
    try:
        # Extract conversation_id from request
        conversation_id = request.conversation_id
        if not conversation_id:
            # Generate a new conversation ID if not provided
            user_email = user.get('email', 'anonymous') if user and isinstance(user, dict) else 'anonymous'
            conversation_id = f"azure_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_email}"
        
        # Get project client from app state
        project_client = app.state.project_client
        
        # Get or create Azure agent
        try:
            agent = app.state.agent
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")
        
        # Use unified memory to get or create Azure thread
        thread = unified_memory.get_or_create_azure_thread(conversation_id, project_client)

        # Enhance query with EDI context if available
        enhanced_query = request.query
        if conversation_id in unified_memory.edi_memories:
            edi_context = unified_memory.get_edi_relevant_context(conversation_id, request.query, max_messages=3)
            if edi_context:
                enhanced_query = f"{edi_context}Current question: {request.query}"
        
        # Create user message in Azure thread
        message = project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=enhanced_query
        )
        
        # Run the agent
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
            # Get the latest assistant message
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
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Azure AI Foundry query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


async def query_edi_transactions(query: EDIQuery, user: Dict = Depends(require_unc_email)):
    """Main endpoint for EDI transaction queries with conversation memory"""
    
    try:
        logger.info(f"EDI query received: {query.question}")
        
        # Generate conversation ID if not provided
        conversation_id = query.conversation_id
        if not conversation_id:
            user_email = user.get('email', 'anonymous') if user and isinstance(user, dict) else 'anonymous'
            conversation_id = f"edi_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_email}"
        
        # Add user message to conversation memory
        conversation_memory.add_message(
            conversation_id, 
            "user", 
            query.question,
            {"query_type": "edi_search", "user_email": user.get('email') if user and isinstance(user, dict) else None}
        )
        
        # Extract parameters from natural language query
        params = edi_search.extract_query_parameters(query.question)
        logger.info(f"Extracted parameters: {params}")
        
        # Search for matching transactions
        transactions = edi_search.search_transactions(params)
        logger.info(f"Found {len(transactions)} transactions")
        
        # Convert to response format
        transaction_results = [
            TransactionResult(
                trace_number=t.get('trace_number', ''),
                amount=t.get('amount', 0.0),
                effective_date=t.get('effective_date', ''),
                originator=t.get('originator', ''),
                receiver=t.get('receiver', ''),
                page_number=t.get('page_number')
            )
            for t in transactions
        ]
        
        # Generate RAG response using LLM with conversation context
        ai_answer = edi_search.generate_rag_response(query.question, transactions, params, conversation_id)
        
        # Add assistant response to conversation memory
        conversation_memory.add_message(
            conversation_id,
            "assistant", 
            ai_answer,
            {
                "query_type": params["query_type"],
                "transactions_found": len(transaction_results),
                "search_performed": True
            }
        )
        
        return EDIResponse(
            answer=ai_answer,
            transactions=transaction_results,
            query_type=params["query_type"],
            search_performed=True
        )
        
    except Exception as e:
        logger.error(f"Error processing EDI query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing EDI query: {str(e)}")



@app.post("/api/edi/analyze")
async def analyze_edi_range(request: EDIAnalysisRequest, user: Dict = Depends(require_unc_email)):
    """Analyze EDI transactions between start and end dates (YYYY-MM-DD)."""
    try:
        loader = EDIDataLoader(request.start, request.end)
        records = loader.load_edi_json(request.start, request.end)
        df = loader.to_dataframe(records)
        analyses = loader.analyze(df)

        # Convert DataFrames to JSON-serializable structures
        def df_to_records(d):
            return [] if d is None or getattr(d, 'empty', True) else d.to_dict(orient="records")

        return {
            "success": True,
            "range": {"start": request.start, "end": request.end},
            "row_count": len(df) if df is not None else 0,
            "analyses": {
                "summary_totals": df_to_records(analyses.get("summary_totals")),
                "daily_totals": df_to_records(analyses.get("daily_totals")),
                "by_originator": df_to_records(analyses.get("by_originator")),
                "by_receiver": df_to_records(analyses.get("by_receiver")),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing EDI range: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing EDI range: {str(e)}")


@app.post("/api/edi/export")
async def export_edi_range(request: EDIAnalysisRequest, user: Dict = Depends(require_unc_email)):
    """Export EDI transactions between start and end dates to Excel and stream the file."""
    try:
        loader = EDIDataLoader(request.start, request.end)
        records = loader.load_edi_json(request.start, request.end)
        df = loader.to_dataframe(records)
        analyses = loader.analyze(df)
        excel_path = loader._default_output_path(request.start, request.end)
        path = loader.export_to_excel(df, analyses, excel_path)

        filename = os.path.basename(path)
        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting EDI range: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error exporting EDI range: {str(e)}")


# # @app.get("/api/edi/conversation/{conversation_id}")
# async def get_conversation_history(conversation_id: str, user: Dict = Depends(require_unc_email)):
#     """Get conversation history for a specific conversation ID"""
    
#     try:
#         history = conversation_memory.get_conversation_history(conversation_id)
        
#         return {
#             "conversation_id": conversation_id,
#             "message_count": len(history),
#             "messages": history,
#             "retrieved_by": user.get('email') if user and isinstance(user, dict) else None
#         }
        
#     except Exception as e:
#         logger.error(f"Error retrieving conversation history: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Error retrieving conversation history: {str(e)}")


@app.get("/api/conversation/{conversation_id}/unified")
async def get_unified_conversation_info(conversation_id: str, user: Dict = Depends(require_unc_email)):
    """Get unified conversation information across both Azure AI Foundry and EDI systems"""
    
    try:
        # Get conversation info from unified memory
        conversation_info = unified_memory.get_conversation_info(conversation_id)
        
        # Get EDI conversation history
        edi_history = unified_memory.get_edi_conversation_history(conversation_id)
        
        # Get Azure thread info if available
        azure_thread_info = None
        if conversation_id in unified_memory.session_threads:
            thread = unified_memory.session_threads[conversation_id]
            azure_thread_info = {
                "thread_id": thread.id,
                "has_thread": True
            }
        else:
            azure_thread_info = {
                "thread_id": None,
                "has_thread": False
            }
        
        return {
            "conversation_id": conversation_id,
            "conversation_info": conversation_info,
            "edi_history": {
                "message_count": len(edi_history),
                "messages": edi_history
            },
            "azure_thread": azure_thread_info,
            "retrieved_by": user.get('email') if user and isinstance(user, dict) else None
        }
        
    except Exception as e:
        logger.error(f"Error retrieving unified conversation info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving unified conversation info: {str(e)}")


# # @app.get("/api/edi/stats")
# async def get_edi_statistics():
#     """Get statistics about the EDI transaction database"""
    
#     if not edi_search.search_client:
#         raise HTTPException(status_code=503, detail="EDI search service not available")
    
#     try:
#         # Get total count
#         count_result = edi_search.search_client.search(
#             search_text="*",
#             include_total_count=True,
#             top=0
#         )
        
#         total_count = count_result.get_count()
        
#         return {
#             "total_transactions": total_count,
#             "service_status": "active",
#             "index_name": os.getenv("AZURE_SEARCH_INDEX_NAME", "edi-transactions")
#         }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error getting statistics: {str(e)}")


# # @app.post("/api/edi/search/amount")
# async def search_by_amount(amount: float, date: Optional[str] = None):
#     """Direct search by amount and optional date"""
    
#     if not edi_search.search_client:
#         raise HTTPException(status_code=503, detail="EDI search service not available")
    
#     try:
#         if date:
#             filter_expr = f"amount eq {amount} and effective_date eq '{date}'"
#         else:
#             filter_expr = f"amount eq {amount}"
            
#         results = edi_search.search_client.search(
#             search_text="",
#             filter=filter_expr,
#             select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
#             top=20
#         )
        
#         return [dict(result) for result in results]
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error searching by amount: {str(e)}")


# Enhanced query endpoint that handles both EDI queries and general AI chat
@app.post("/api/chat")
async def enhanced_chat(request: QueryRequest, user: Dict = Depends(require_unc_email)):
    """Enhanced chat endpoint that handles both EDI queries and general AI chat with unified memory"""
    
    # Ensure we have a conversation_id
    conversation_id = request.conversation_id
    if not conversation_id:
        user_email = user.get('email', 'anonymous') if user and isinstance(user, dict) else 'anonymous'
        conversation_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_email}"
    
    # # Use AI to triage the query to the appropriate agent
    # route_decision = await triage_query(request.query)

    if request.mode == "EDI":
        # Route to EDI search with conversation context
        edi_query = EDIQuery(
            question=request.query,
            conversation_id=conversation_id,
            messages=request.messages
        )
        edi_response = await query_edi_transactions(edi_query)

        return {
            "response": edi_response.answer,
            "type": "edi_search",
            "transactions_found": len(edi_response.transactions),
            "data": edi_response.transactions,
            "conversation_id": conversation_id
        }
    else:
        # Route to existing AI agent with unified memory
        ai_response = await query(request)
        return {
            "response": ai_response["answer"],
            "type": "general_ai",
            "sources": ai_response["sources"],
            "conversation_id": ai_response["conversation_id"]
        }


# # @app.post("/api/edi-preprocess")
# async def edi_preprocess(request: Request):
#     """Connect to Azure Blob Storage, then run the edi_preprocessor.py script to preprocess the EDI transactions in the blob storage"""

#     # Connect to Azure Blob Storage
#     blob_service_client = AzureBlobContainerClient(os.getenv("AZURE_STORAGE_CONNECTION_STRING"), os.getenv("AZURE_STORAGE_CONTAINER_NAME"))
#     container_client = blob_service_client.get_container_client(os.getenv("AZURE_STORAGE_CONTAINER_NAME"))

#     # Run the edi_preprocessor.py script to preprocess the EDI transactions in the blob storage
#     edi_preprocessor = EDIProcessor()
#     edi_preprocessor.preprocess_edi_transactions()


#     return {
#         "message": "EDI transactions preprocessed"
#     }


@app.post("/api/upload-edi-report")
async def upload_edi_report(
    file: UploadFile = File(...),
    user: Dict = Depends(require_unc_email)
):
    """Upload EDI report to Azure Blob Storage"""

    try:
        # Validate file type
        allowed_extensions = {'.pdf', '.txt', '.csv', '.xlsx', '.xls'}
        file_extension = os.path.splitext(file.filename)[1].lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type {file_extension} not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )

        # Read file content
        file_content = await file.read()

        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")

        # Initialize Azure Blob client for edi-reports container
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = "edi-reports"

        if not connection_string:
            raise HTTPException(status_code=500, detail="Azure Storage configuration not found")

        blob_client = AzureBlobContainerClient(connection_string, container_name)

        # Use original filename to allow Azure's duplicate detection to work
        blob_name = file.filename

        # Upload to Azure Blob Storage - let Azure handle duplicates
        try:
            blob_client.upload_blob(blob_name, file_content, overwrite=False)
        except Exception as upload_error:
            # If file already exists, Azure will raise an exception
            if "BlobAlreadyExists" in str(upload_error) or "already exists" in str(upload_error).lower():
                raise HTTPException(
                    status_code=409,
                    detail=f"File '{file.filename}' already exists in the container"
                )
            else:
                raise upload_error

        user_email = user.get('email', 'unknown') if user and isinstance(user, dict) else 'unknown'
        logger.info(f"File uploaded successfully: {blob_name} by user {user_email}")

        return {
            "success": True,
            "message": "File uploaded successfully",
            "filename": file.filename,
            "blob_name": blob_name,
            "size": len(file_content),
            "uploaded_by": user.get('email') if user and isinstance(user, dict) else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@app.post("/api/update-search-index")
async def update_search_index(user: Dict = Depends(require_unc_email)):
    """Update search index with new EDI files incrementally"""

    try:
        user_email = user.get('email', 'unknown') if user and isinstance(user, dict) else 'unknown'
        logger.info(f"Starting incremental search index update requested by {user_email}")

        # Initialize the incremental updater
        updater = IncrementalIndexUpdater()

        # Perform the incremental update
        result = updater.perform_incremental_update()

        if result["success"]:
            logger.info(f"Incremental update completed: {result['message']}")
            return {
                "success": True,
                "message": result["message"],
                "details": {
                    "new_files_processed": result.get("new_files_count", 0),
                    "transactions_added": result.get("transactions_added", 0),
                    "processed_files": result.get("processed_files", [])
                },
                "updated_by": user.get('email') if user and isinstance(user, dict) else None
            }
        else:
            logger.error(f"Incremental update failed: {result['message']}")
            raise HTTPException(
                status_code=500,
                detail=f"Search index update failed: {result['message']}"
            )

    except Exception as e:
        logger.error(f"Error in incremental search index update: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update search index: {str(e)}"
        )


# # @app.get("/api/search-index-status")
# async def get_search_index_status(user: Dict = Depends(require_unc_email)):
#     """Get current search index status and information about new files"""

#     try:
#         updater = IncrementalIndexUpdater()

#         # Find new files without processing them
#         new_files, registry = updater.find_new_and_updated_files()

#         # Get search index statistics
#         search_service = updater.get_search_service()
#         search_stats = search_service.get_statistics()

#         return {
#             "success": True,
#             "search_index": {
#                 "total_transactions": search_stats.get("total_transactions", 0),
#                 "earliest_date": search_stats.get("earliest_date"),
#                 "latest_date": search_stats.get("latest_date"),
#                 "index_name": search_stats.get("index_name")
#             },
#             "pending_updates": {
#                 "new_files_count": len(new_files),
#                 "new_files": new_files[:10] if new_files else [],  # Show first 10 files
#                 "has_more": len(new_files) > 10
#             },
#             "last_registry_info": {
#                 "total_processed_files": len(registry),
#                 "last_update": max([info.processed_at for info in registry.values()]) if registry else None
#             }
#         }

#     except Exception as e:
#         logger.error(f"Error getting search index status: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get search index status: {str(e)}"
#         )


# Session management endpoints for Cosmos DB
@app.get("/api/sessions/{user_id}")
async def get_user_sessions(user_id: str, user: Dict = Depends(require_unc_email)):
    """Get all sessions for a specific user"""
    try:
        sessions = cosmos_client.get_sessions_for_user_id(user_id)
        return {
            "user_id": user_id,
            "sessions": sessions,
            "count": len(sessions)
        }
    except Exception as e:
        logger.error(f"Error getting sessions for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting sessions: {str(e)}")

@app.get("/api/session/{session_id}")
async def get_session(session_id: str, user: Dict = Depends(require_unc_email)):
    """Get a specific session with its messages"""
    try:
        session = cosmos_client.get_session(session_id)
        return {
            "session": session,
            "message_count": len(session.get('messages', [])),
            "retrieved_by": user.get('email') if user and isinstance(user, dict) else None
        }
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting session: {str(e)}")

@app.post("/api/session")
async def create_session(request: Request, user: Dict = Depends(require_unc_email)):
    """Create a new session"""
    try:
        data = await request.json()
        session_id = data.get('session_id')
        user_id = data.get('user_id', user.get('email'))
        title = data.get('title', 'New Chat')
        
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        
        session = cosmos_client.create_new_session(session_id, user_id, title)
        return {
            "session": session,
            "message": "Session created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")

@app.put("/api/session/{session_id}")
async def update_session(session_id: str, request: Request, user: Dict = Depends(require_unc_email)):
    """Update a session (add messages, rename, etc.)"""
    try:
        data = await request.json()
        user_id = data.get('user_id', user.get('email'))
        messages = data.get('messages')
        title = data.get('title')
        
        session = cosmos_client.update_session(session_id, user_id, messages, title)
        return {
            "session": session,
            "message": "Session updated successfully"
        }
    except Exception as e:
        logger.error(f"Error updating session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating session: {str(e)}")

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str, user: Dict = Depends(require_unc_email)):
    """Delete a session"""
    try:
        cosmos_client.delete_session(session_id)
        return {
            "message": "Session deleted successfully",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")


if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["**/networkx/**"]
    )