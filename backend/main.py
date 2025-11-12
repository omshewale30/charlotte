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
import pandas as pd
import numpy as np
from auth import get_current_user, require_unc_email, get_optional_user
from azure.azure_blob_container_client import AzureBlobContainerClient
from azure.azure_client import AzureClient
from edi_search_integration import EDISearchIntegration
from chs_edi_json_to_excel import CHS_EDI_DataLoader
from master_edi_json_to_excel import MASTER_EDI_DataLoader
from align_rx_json_to_excel import AlignRxDataLoader
from alignRx_parser import AlignRxParser, DuplicateReportError as AlignRxDuplicateReportError
from concurrent.futures import ThreadPoolExecutor
import asyncio
from edi_parser import EDIParser, DuplicateReportError
# Load environment variables from .env file
load_dotenv()

# Initialize Azure OpenAI client for query triaging
azure_openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
    azure_endpoint=os.getenv("AZURE_AI_RESOURCE_ENDPOINT")
)


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
from align_rx_json_to_excel import AlignRxDataLoader
from azure.azure_alignRx_search_setup import AlignRxSearchService
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
    mode: str


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

# ThreadPoolExecutor for running synchronous blob operations
executor = ThreadPoolExecutor(max_workers=4)

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
async def analyze_edi_range(request: EDIAnalysisRequest,user: Dict = Depends(require_unc_email)):
    """Analyze EDI transactions between start and end dates (YYYY-MM-DD)."""
    try:
        if request.mode == "master":
            loader = MASTER_EDI_DataLoader(request.start, request.end)
        else:
            loader = CHS_EDI_DataLoader(request.start, request.end)

        records = loader.load_edi_json(request.start, request.end)
        df = loader.to_dataframe(records)
        analyses = loader.analyze(df)

        # Convert DataFrames to JSON-serializable structures
        def df_to_records(d):
            if d is None or getattr(d, 'empty', True):
                return []
            # Convert to dict first, then replace NaN values with None for JSON serialization
            records = d.to_dict(orient="records")
            # Clean NaN values and convert date objects to strings
            cleaned_records = []
            for record in records:
                cleaned_record = {}
                for key, value in record.items():
                    # Check if value is NaN using pandas isna (handles all NaN types)
                    if pd.isna(value):
                        cleaned_record[key] = None
                    # Convert date objects to strings (YYYY-MM-DD format)
                    elif hasattr(value, 'strftime'):
                        cleaned_record[key] = value.strftime("%Y-%m-%d")
                    else:
                        cleaned_record[key] = value
                cleaned_records.append(cleaned_record)
            return cleaned_records

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



@app.post("/api/alignrx/analyze")
async def analyze_alignrx_range(request: EDIAnalysisRequest, user: Dict = Depends(require_unc_email)):
    """Analyze AlignRx reports between start and end dates (YYYY-MM-DD)."""
    try:
        loader = AlignRxDataLoader(request.start, request.end)
        records = loader._load_search_records(request.start, request.end)
        df = loader.to_dataframe(records)
        analyses = loader.analyze(df)
        # Convert DataFrames to JSON-serializable structures
        def df_to_records(d):
            if d is None or getattr(d, 'empty', True):
                return []
            # Convert to dict first, then replace NaN values with None for JSON serialization
            records = d.to_dict(orient="records")
            # Clean NaN values and convert date objects to strings
            cleaned_records = []
            for record in records:
                cleaned_record = {}
                for key, value in record.items():
                    # Check if value is NaN using pandas isna (handles all NaN types)
                    if pd.isna(value):
                        cleaned_record[key] = None
                    # Convert date objects to strings (YYYY-MM-DD format)
                    elif hasattr(value, 'strftime'):
                        cleaned_record[key] = value.strftime("%Y-%m-%d")
                    else:
                        cleaned_record[key] = value
                cleaned_records.append(cleaned_record)
            return cleaned_records

        return {
            "success": True,
            "range": {"start": request.start, "end": request.end},
            "row_count": len(df) if df is not None else 0,
            "analyses": {
                "summary_totals": df_to_records(analyses.get("summary_totals")),
                "daily_totals": df_to_records(analyses.get("daily_totals")),
                "by_destination": df_to_records(analyses.get("by_destination")),
                "by_sender": df_to_records(analyses.get("by_sender")),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing AlignRx range: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing AlignRx range: {str(e)}") 


@app.post("/api/alignrx/export")
async def export_alignrx_range(request: EDIAnalysisRequest, user: Dict = Depends(require_unc_email)):
    """Export AlignRx reports between start and end dates to Excel and stream the file."""
    try:
        loader = AlignRxDataLoader(request.start, request.end)
        records = loader._load_search_records(request.start, request.end)
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
        logger.error(f"Error exporting AlignRx range: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error exporting AlignRx range: {str(e)}")

@app.post("/api/edi/export")
async def export_edi_range(request: EDIAnalysisRequest, user: Dict = Depends(require_unc_email)):
    """Export EDI transactions between start and end dates to Excel and stream the file."""
    try:
        if request.mode == "master":
            loader = MASTER_EDI_DataLoader(request.start, request.end)
        else:
            loader = CHS_EDI_DataLoader(request.start, request.end)
            
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




# Enhanced query endpoint that handles both EDI queries and general AI chat
@app.post("/api/chat")
async def enhanced_chat(request: QueryRequest, user: Dict = Depends(require_unc_email)):
    """Enhanced chat endpoint that handles both EDI queries and general AI chat with unified memory"""
    
    # Ensure we have a conversation_id
    conversation_id = request.conversation_id
    if not conversation_id:
        user_email = user.get('email', 'anonymous') if user and isinstance(user, dict) else 'anonymous'
        conversation_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_email}"
    


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

@app.post("/api/alignrx/upload-report")
async def upload_alignrx_report(
    file: UploadFile = File(...),
    user: Dict = Depends(require_unc_email)
):
    """Upload AlignRx Excel report, parse it, and index parsed data into Azure AI Search."""

    try:
        # Validate file type (AlignRx reports are Excel)
        allowed_extensions = {'.xlsx', '.xls'}
        file_extension = os.path.splitext(file.filename)[1].lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type {file_extension} not allowed. Allowed types: {', '.join(sorted(allowed_extensions))}"
            )
        

        # Read file content
        file_content = await file.read()

        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")

        # Persist to a temporary file for parser consumption
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
            tmp.write(file_content)
            temp_path = tmp.name

        parsed_record = None
        parse_error = None
        is_duplicate_in_index = False
        schema_validation_failed = False
        try:
            parser = AlignRxParser()
            parsed_record = parser.parse_excel_report(temp_path)
        except DuplicateReportError as dup_error:
            # Report already exists in search index - handle gracefully
            is_duplicate_in_index = True
            parse_error = str(dup_error)
            logger.info(f"AlignRx report already exists in search index: {file.filename}")
        except ValueError as validation_error:
            # Schema mismatch - parsing incomplete (missing required fields)
            schema_validation_failed = True
            parse_error = str(validation_error)
            logger.warning(f"Schema validation failed for {file.filename}: {parse_error}")
        except Exception as e:
            parse_error = str(e)
        finally:
            try:
                os.remove(temp_path)
            except Exception:
                pass

        # If parsing failed due to schema validation, reject immediately without uploading blob
        if schema_validation_failed:
            raise HTTPException(
                status_code=422,
                detail=f"Schema validation failed: {parse_error}. The file does not match the expected AlignRx report format."
            )

        # If parsing failed for other reasons (not schema validation), also reject
        if not parsed_record:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to parse AlignRx report{': ' + parse_error if parse_error else ''}"
            )

        # If report already exists in search index, reject without uploading blob
        if is_duplicate_in_index:
            raise HTTPException(
                status_code=409,
                detail=f"Report already exists in search index. The file data matches an existing report with the same date, destination, and payment amount."
            )

        # Initialize Azure Blob client for alignrx-reports container
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = "alignrx-reports"

        if not connection_string:
            raise HTTPException(status_code=500, detail="Azure Storage configuration not found")

        blob_client = AzureBlobContainerClient(connection_string, container_name)

        # Use original filename so Azure duplicate detection can work
        blob_name = file.filename

        # Upload the raw file to Blob Storage (no overwrite)
        # Only upload if parsing succeeded
        # Run blob operations in executor with timeout to avoid blocking the event loop
        try:
            blob_client.upload_blob(blob_name, file_content, overwrite=False)
            duplicate = False
        except Exception as upload_error:
            if "BlobAlreadyExists" in str(upload_error) or "already exists" in str(upload_error).lower():
                # File already exists in blob storage
                raise HTTPException(
                    status_code=409,
                    detail=f"File '{file.filename}' already exists in the container"
                )
            else:
                raise upload_error

        # Enrich parsed record with storage metadata
        try:
            blob_url = blob_client.get_blob_url(blob_name)
        except Exception:
            blob_url = None
        
        

        # Ensure the indexed source_file reflects the actual uploaded blob, not a temp path used for parsing
        parsed_record["source_file"] = blob_name
        parsed_record["blob_name"] = blob_name
        if blob_url:
            parsed_record["blob_url"] = blob_url
        parsed_record["uploaded_at"] = datetime.utcnow().isoformat() + "Z"
        if user and isinstance(user, dict):
            parsed_record["uploaded_by"] = user.get("email")
        
    

        # Prepare and upload parsed document to Azure AI Search (AlignRx index)
        # Run indexing in executor to avoid blocking the event loop
        index_success = False
        try:
            # Normalize fields to match index schema
            index_doc = {
                "report_id": parsed_record.get("report_id") or parsed_record.get("id"),
                "source_file": parsed_record.get("source_file") or blob_name,
                "pay_date": parsed_record.get("pay_date") or parsed_record.get("date"),
                "destination": parsed_record.get("destination"),
                "processing_fee": parsed_record.get("processing_fee"),
                "payment_amount": parsed_record.get("payment_amount"),
                "central_payments": parsed_record.get("central_payments") or [],
            }

            # Remove keys with None to avoid schema mismatches
            index_doc = {k: v for k, v in index_doc.items() if v is not None}

            alignrx_search = AlignRxSearchService()
            index_success = alignrx_search.upload_documents([index_doc])
        except Exception as e:
            logger.error(f"Error uploading parsed AlignRx document to search index: {str(e)}")
            # Do not fail the entire request if indexing fails; report partial success

        user_email = user.get('email', 'unknown') if user and isinstance(user, dict) else 'unknown'
        logger.info(f"AlignRx report processed: {blob_name} by user {user_email}; indexed={index_success}")

        return {
            "success": True,
            "message": "AlignRx report uploaded and processed",
            "duplicate": duplicate,
            "filename": file.filename,
            "blob_name": blob_name,
            "blob_url": blob_url,
            "parsed": parsed_record,
            "indexed": index_success
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading AlignRx report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload AlignRx report: {str(e)}")

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

        blob_client = AzureBlobContainerClient(os.getenv("AZURE_STORAGE_CONNECTION_STRING"), "master-edi-reports")
        if blob_client.container_client.get_blob_client(file.filename).exists():
            raise HTTPException(status_code=409, detail=f"File '{file.filename}' already exists in the container")

        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Save to temporary file for parsing
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
            tmp.write(file_content)
            temp_path = tmp.name
        
        parse_result = None
        parse_error = None
        is_file_duplicate = False
        chs_index_success = False
        all_index_success = False
        blob_name = file.filename

        try:
            parser = EDIParser()
            parse_result = parser.parse_edi_file(temp_path, blob_name)
       
            
            if not parse_result.get("chs_transactions"):
                logger.warning(f"No CHS transactions found in {blob_name}")

        
        # File-level duplicate: entire file already exists - reject completely
        except DuplicateReportError as dup_error:
            # Report already exists in search index - handle gracefully
            is_file_duplicate = True
            parse_error = str(dup_error)
            logger.info(f"EDI report already exists in search index: {file.filename}")
        except Exception as e:
            parse_error = str(e)
            logger.error(f"Error parsing EDI file: {parse_error}")
        finally:
            try:
                os.remove(temp_path)
            except Exception:
                pass
        
        if not parse_result or not parse_result.get("all_transactions"):
            raise HTTPException(
                status_code=422,
                detail=f"Failed to parse EDI report{': ' + parse_error if parse_error else ''}"
            )
        
        # If entire file is duplicate, reject the upload
        if is_file_duplicate:
            raise HTTPException(
                status_code=409,
                detail=f"Report already exists in search index: {parse_error}"
            )

        # Extract data from parse result
        all_transactions = parse_result.get("all_transactions", [])
        chs_transactions = parse_result.get("chs_transactions", [])
        chs_duplicate = parse_result.get("chs_duplicate", False)
        all_duplicate = parse_result.get("all_duplicate", False)
        
        # If all transactions are duplicates, reject the upload completely (no blob upload)
        if all_duplicate:
            raise HTTPException(
                status_code=409,
                detail=f"All transactions from file '{file.filename}' already exist in the master-edi search index. File upload rejected."
            )
        
        # Upload to Azure Blob Storage (after successful parsing and duplicate check)
        # Only upload if all_duplicate is false
        sample_transaction = all_transactions[0]
        sum_amount = sum(transaction.get("amount", 0) for transaction in all_transactions)
        metadata = {
            "effective_date": sample_transaction.get("effective_date", ""),
            "total_amount": sum_amount
        }
        # Azure Blob Storage only allows metadata values as strings.
        # Ensure all metadata values are string type.
        str_metadata = {k: str(v) for k, v in metadata.items()}
        blob_client.upload_blob(blob_name, file_content, overwrite=False)
        blob_client.set_blob_metadata(blob_name, str_metadata)
        logger.info(f"File uploaded to blob storage: {blob_name} with metadata: {metadata}")

        # Index transactions in search index
        # Skip CHS indexing if trace numbers are duplicates
        if chs_duplicate:
            logger.warning(f"Skipping CHS transaction indexing due to duplicate trace numbers in CHS search index")
            chs_index_success = False  # Explicitly set to False since we're skipping
        elif chs_transactions:
            chs_index_success = parser.index_transactions(chs_transactions, blob_name, "edi-transactions")
        
        # Index all transactions to master-edi (all_duplicate check already handled above - upload rejected if true)
        if all_transactions:
            all_index_success = parser.index_transactions(all_transactions, blob_name, "master-edi")

        # Consider it successful if both indexes were updated successfully or if duplicates prevented CHS indexing
        # Note: all_duplicate is already handled above (upload rejected), so we won't reach here if all_duplicate is true
        index_success = (
            (chs_index_success or chs_duplicate or not chs_transactions) and 
            all_index_success
        )

        if index_success:
            if chs_duplicate:
                logger.info(f"Successfully indexed {len(all_transactions)} all transactions from {blob_name} (CHS transactions skipped due to duplicates)")
            else:
                logger.info(f"Successfully indexed {len(chs_transactions) if chs_transactions else 0} CHS transactions and {len(all_transactions)} all transactions from {blob_name}")
        else:
            logger.warning(f"Failed to index transactions from {blob_name}")

        user_email = user.get('email', 'unknown') if user and isinstance(user, dict) else 'unknown'
        logger.info(f"EDI report processed: {blob_name} by user {user_email}; indexed={index_success}")

        # Build message based on duplicate status
        # Note: all_duplicate is already handled above (upload rejected), so we won't reach here if all_duplicate is true
        message = "File uploaded and processed successfully"
        if chs_duplicate:
            message += " (CHS transactions skipped due to duplicates)"
        
        return {
            "success": True,
            "message": message,
            "filename": file.filename,
            "blob_name": blob_name,
            "size": len(file_content),
            "chs_transaction_count": len(chs_transactions) if chs_transactions else 0,
            "all_transaction_count": len(all_transactions) if all_transactions else 0,
            "chs_indexed": chs_index_success,
            "chs_duplicate": chs_duplicate,
            "all_indexed": all_index_success,
            "all_duplicate": False,  # If we reach here, all_duplicate is false (upload would have been rejected otherwise)
            "uploaded_by": user.get('email') if user and isinstance(user, dict) else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@app.post("/api/update-search-index")
async def update_search_index(user: Dict = Depends(require_unc_email)):
    """We do not need this endpoint anymore as we are updating the search index as we upload the EDI reports
    
    
    """

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


@app.get("/api/edi/reports")
async def get_edi_reports(user: Dict = Depends(require_unc_email)):
    """Get list of EDI reports from Azure Blob Storage"""
    try:
        # Initialize Azure Blob client for edi-reports container
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = "edi-reports"

        if not connection_string:
            raise HTTPException(status_code=500, detail="Azure Storage configuration not found")

        blob_client = AzureBlobContainerClient(connection_string, container_name)
        
        # List all blobs in the container
        blobs = blob_client.list_blobs()
        
        reports = []
        for blob in blobs:
            # Extract metadata from filename if it follows the pattern
            # EDI Remittance Advice Report_2063_20250819_chs.pdf
            filename = blob.name
            blob_props = blob_client.get_blob_properties(filename)
            
            # Parse filename to extract date and other info
            import re
            date_match = re.search(r'(\d{8})', filename)  # Extract YYYYMMDD
            amount_match = re.search(r'(\d+\.\d{2})', filename)  # Extract amount if present
            
            parsed_date = None
            if date_match:
                date_str = date_match.group(1)
                try:
                    parsed_date = datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
                except ValueError:
                    parsed_date = None
            
            reports.append({
                "filename": filename,
                "url": blob_client.get_blob_url(filename),
                "size": blob_props.size,
                "last_modified": blob_props.last_modified.isoformat() if blob_props.last_modified else None,
                "parsed_date": parsed_date,
                "content_type": blob_props.content_settings.content_type if blob_props.content_settings else "application/pdf"
            })
        
        # Sort by last modified date (newest first)
        reports.sort(key=lambda x: x["last_modified"] or "", reverse=True)
        
        return {
            "success": True,
            "reports": reports,
            "total_count": len(reports),
            "retrieved_by": user.get('email') if user and isinstance(user, dict) else None
        }
        
    except Exception as e:
        logger.error(f"Error retrieving EDI reports: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve EDI reports: {str(e)}")


@app.get("/api/edi/reports/{filename}")
async def get_edi_report(filename: str, user: Dict = Depends(require_unc_email)):
    """Get a specific EDI report file from Azure Blob Storage"""
    try:
        # Initialize Azure Blob client for edi-reports container
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = "edi-reports"

        if not connection_string:
            raise HTTPException(status_code=500, detail="Azure Storage configuration not found")

        blob_client = AzureBlobContainerClient(connection_string, container_name)
        
        # Get blob content
        blob_content = blob_client.download_blob(filename)
        
        # Get blob properties for content type
        blob_props = blob_client.get_blob_properties(filename)
        content_type = blob_props.content_settings.content_type if blob_props.content_settings else "application/pdf"
        
        # Return file response
        from fastapi.responses import Response
        return Response(
            content=blob_content.readall(),
            media_type=content_type,
            headers={"Content-Disposition": f"inline; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving EDI report {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve EDI report: {str(e)}")




if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["**/networkx/**"]
    )