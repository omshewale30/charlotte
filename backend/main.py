from fastapi import FastAPI, HTTPException, Depends, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
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
from auth import msal_auth, get_current_user, require_unc_email, get_optional_user
from edi_preprocessor import EDIProcessor
from azure_blob_container_client import AzureBlobContainerClient
from incremental_index_updater import IncrementalIndexUpdater

# Load environment variables from .env file
load_dotenv()

# Azure imports
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
from azure.identity import ClientSecretCredential
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
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
    messages: Optional[List[Message]] = None

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

# Auth-related models
class AuthURL(BaseModel):
    auth_url: str
    state: str

class AuthCallback(BaseModel):
    session_id: str
    user: Dict
    expires_at: str

class UserInfo(BaseModel):
    id: str
    email: str
    name: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    office_location: Optional[str] = None


# EDI Search Service Integration
class EDISearchIntegration:
    """Integration class for EDI search in Charlotte"""
    
    def __init__(self):
        self.search_client = None
        self.setup_search_client()
    
    def setup_search_client(self):
        """Initialize Azure Search client"""
        try:
            endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
            api_key = os.getenv("AZURE_SEARCH_API_KEY") 
            index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "edi-transactions")
            
            if endpoint and api_key:
                credential = AzureKeyCredential(api_key)
                self.search_client = SearchClient(
                    endpoint=endpoint,
                    index_name=index_name,
                    credential=credential
                )
        except Exception as e:
            logger.warning(f"Could not initialize Azure Search client: {e}")
    
    def extract_query_parameters(self, question: str) -> Dict:
        """Extract structured parameters from natural language query using AI"""
        try:
            # Setup OpenAI client for Azure
            openai_client = AzureOpenAI(
                api_version="2024-12-01-preview",
                api_key=os.getenv("AZURE_OPENAI_KEY"),
                azure_endpoint="https://charlotte-ai-resource.openai.azure.com/",
            )
            
            # Prompt for parameter extraction
            system_prompt = """You are an expert at extracting structured data from natural language queries about financial transactions.

Extract the following information from the user's query and return it as valid JSON:
- amount: float or null (exact monetary amount like $92.39, 103.12 dollars, etc.)
- amount_min: float or null (minimum amount for range queries like "over $100", "more than $50")  
- amount_max: float or null (maximum amount for range queries like "under $200", "less than $100")
- date: string in YYYY-MM-DD format or null (specific dates like "June 2, 2025", "2nd June 2025", "6/2/2025")
- date_start: string in YYYY-MM-DD format or null (start date for ranges like "in June 2025", "from January")
- date_end: string in YYYY-MM-DD format or null (end date for ranges like "in June 2025", "until March")
- trace_number: string or null (specific transaction identifier - only if user provides one, NOT if they're asking for it)
- originator: string or null (company names like BCBS, Blue Cross, United Healthcare, etc.)
- query_type: string (one of: "count_all", "all_in_period", "amount_range", "date_range", "trace_search", "originator_search", "specific_lookup", "general")

Query type rules:
- Use "count_all" for queries asking about total number, count, or "how many" transactions in database
- Use "all_in_period" for queries like "all transactions in June", "show me transactions for 2025", "all payments in Q1"
- Use "amount_range" for amount-based queries like "transactions over $100", "payments between $50-$200"
- Use "date_range" for date-based queries like "transactions from Jan to March", "payments last month"
- Use "trace_search" only when user provides a specific trace number to look up
- Use "originator_search" when searching by company name
- Use "specific_lookup" when user asks for specific details about exact amounts/dates
- Use "general" for questions that don't fit other categories

Return only valid JSON, no other text."""

            user_prompt = f"Extract parameters from this query: {question}"
            
            response = openai_client.chat.completions.create(
                model=os.getenv("SMALL_MODEL_NAME", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=200

            )
            
            # Parse the AI response
            ai_response = response.choices[0].message.content.strip()
            logger.info(f"AI parameter extraction response: {ai_response}")
            
            # Clean JSON response (remove markdown formatting if present)
            json_text = ai_response
            if json_text.startswith('```json'):
                json_text = json_text.replace('```json', '').replace('```', '').strip()
            elif json_text.startswith('```'):
                json_text = json_text.replace('```', '').strip()
            
            # Parse JSON response
            params = json.loads(json_text)
            
            # Validate and set defaults
            default_params = {
                "amount": None,
                "amount_min": None,
                "amount_max": None,
                "date": None,
                "date_start": None,
                "date_end": None,
                "trace_number": None,
                "originator": None,
                "query_type": "general"
            }
            
            # Merge with defaults
            for key in default_params:
                if key not in params or params[key] == "":
                    params[key] = default_params[key]
            
            logger.info(f"Extracted parameters: {params}")
            return params
            
        except Exception as e:
            logger.error(f"Error in AI parameter extraction: {e}")
            # Fallback to basic parameters
            return {
                "amount": None,
                "amount_min": None,
                "amount_max": None,
                "date": None,
                "date_start": None,
                "date_end": None,
                "trace_number": None,
                "originator": None,
                "query_type": "general"
            }
    
    def search_transactions(self, params: Dict) -> List[Dict]:
        """Search for transactions based on extracted parameters using flexible filters"""
        if not self.search_client:
            logger.warning("Search client not available")
            return []
        
        logger.info(f"Searching with params: {params}")
        
        try:
            filter_conditions = []
            search_text = ""
            top_count = 100  # Default limit
            
            # Build filter conditions based on parameters
            if params.get("amount"):
                filter_conditions.append(f"amount eq {params['amount']}")
            
            if params.get("amount_min"):
                filter_conditions.append(f"amount ge {params['amount_min']}")
                
            if params.get("amount_max"):
                filter_conditions.append(f"amount le {params['amount_max']}")
            
            if params.get("date"):
                filter_conditions.append(f"effective_date eq '{params['date']}'")
                
            if params.get("date_start"):
                filter_conditions.append(f"effective_date ge '{params['date_start']}'")
                
            if params.get("date_end"):
                filter_conditions.append(f"effective_date le '{params['date_end']}'")
            
            if params.get("trace_number"):
                filter_conditions.append(f"trace_number eq '{params['trace_number']}'")
                top_count = 1  # Only need one result for specific trace
            
            if params.get("originator"):
                # Use search text for originator to allow partial matches
                search_text = params["originator"]
                
            # Handle special query types
            if params.get("query_type") == "count_all":
                results = self.search_client.search(
                    search_text="*",
                    include_total_count=True,
                    top=0
                )
                total_count = results.get_count()
                logger.info(f"Total transactions count: {total_count}")
                return [{"total_count": total_count, "query_type": "count_all"}]
            
            # If asking for all transactions (e.g., "all transactions in June")
            if params.get("query_type") == "all_in_period":
                top_count = 1000  # Increase limit for period queries
            
            # Build final filter expression
            filter_expr = " and ".join(filter_conditions) if filter_conditions else None
            
            logger.info(f"Filter expression: {filter_expr}")
            logger.info(f"Search text: '{search_text}'")
            logger.info(f"Top count: {top_count}")
            
            # Execute search
            search_params = {
                "search_text": search_text,
                "select": ["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                "top": top_count,
                "include_total_count": True
            }
            
            if filter_expr:
                search_params["filter"] = filter_expr
                
            if search_text and params.get("originator"):
                search_params["search_fields"] = ["originator"]
            
            results = self.search_client.search(**search_params)
            
            # Convert results to list
            result_list = [dict(result) for result in results]
            total_found = results.get_count() if hasattr(results, 'get_count') else len(result_list)
            
            logger.info(f"Search returned {len(result_list)} results out of {total_found} total matches")
            
            # Add metadata about the search
            if result_list:
                result_list[0]["_search_metadata"] = {
                    "total_matches": total_found,
                    "returned_count": len(result_list),
                    "query_params": params
                }
            
            return result_list
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def prepare_context(self, transactions: List[Dict]) -> str:
        """Prepare transaction data as context for the LLM"""
        if not transactions:
            return "No transactions found."
            
        # Handle count_all queries
        if len(transactions) == 1 and "total_count" in transactions[0]:
            return f"Total transactions in database: {transactions[0]['total_count']}"
        
        # Filter out metadata from first transaction if present
        clean_transactions = []
        for t in transactions:
            if "_search_metadata" in t:
                metadata = t.pop("_search_metadata")
                # Use metadata for summary if needed
            clean_transactions.append(t)
        
        # Format transactions as structured context
        context_parts = []
        context_parts.append(f"Found {len(clean_transactions)} transactions:\n")
        
        for i, t in enumerate(clean_transactions[:50], 1):  # Limit to first 50 for context
            context_parts.append(
                f"{i}. Trace: {t.get('trace_number', 'N/A')}, "
                f"Amount: ${t.get('amount', 0):.2f}, "
                f"Date: {t.get('effective_date', 'N/A')}, "
                f"From: {t.get('originator', 'N/A')}, "
                f"To: {t.get('receiver', 'N/A')}"
            )
        
        if len(clean_transactions) > 50:
            context_parts.append(f"\n... and {len(clean_transactions) - 50} more transactions")
            
        return "\n".join(context_parts)
    
    def generate_rag_response(self, question: str, transactions: List[Dict], params: Dict) -> str:
        """Generate RAG response by feeding transaction context to LLM"""
        try:
            # Setup OpenAI client
            openai_client = AzureOpenAI(
                api_version="2024-12-01-preview",
                api_key=os.getenv("AZURE_OPENAI_KEY"),
                azure_endpoint="https://charlotte-ai-resource.openai.azure.com/",
            )
            
            # Prepare context from transactions
            context = self.prepare_context(transactions)
            
            # Handle special cases
            if not transactions:
                return "I couldn't find any transactions matching your query. Please check the criteria and try again."
            
            # Handle count queries
            if len(transactions) == 1 and "total_count" in transactions[0]:
                count = transactions[0]["total_count"]
                return f"I have **{count:,}** EDI transactions in the database."
            
            # Create system prompt for RAG response
            system_prompt = """You are a financial transaction assistant with access to EDI transaction data. 
            
Your task is to analyze the provided transaction data and answer the user's question comprehensively.

Guidelines:
- Use the exact transaction data provided in the context
- Be precise with numbers, dates, and amounts
- Format monetary amounts clearly (e.g., $1,234.56)
- If multiple transactions match, provide summaries and key insights
- For date ranges, provide totals and breakdowns when relevant
- Use **bold** for important numbers and key information
- If the user asks for specific trace numbers, provide them clearly
- If patterns emerge in the data, highlight them

Transaction Data Context:
{context}

Answer the user's question based on this transaction data."""

            user_prompt = f"User's question: {question}\n\nPlease analyze the transaction data and provide a comprehensive answer."
            
            response = openai_client.chat.completions.create(
                model=os.getenv("SMALL_MODEL_NAME", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt.format(context=context)},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            ai_response = response.choices[0].message.content.strip()
            logger.info(f"RAG response generated: {ai_response[:200]}...")
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Error generating RAG response: {e}")
            return "I encountered an error while analyzing the transaction data. Please try again."


# Initialize the EDI search integration
edi_search = EDISearchIntegration()


def setup_azure_client():
    project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    tenant_id = os.getenv("AZURE_AD_TENANT_ID")
    client_id = os.getenv("AZURE_AD_CLIENT_ID")
    client_secret = os.getenv("AZURE_AD_CLIENT_SECRET")

        # Check for missing environment variables
    missing_vars = []
    if not project_endpoint:
        missing_vars.append("AZURE_AI_PROJECT_ENDPOINT")
    if not tenant_id:
        missing_vars.append("AZURE_AD_TENANT_ID")
    if not client_id:
        missing_vars.append("AZURE_AD_CLIENT_ID")
    if not client_secret:
        missing_vars.append("AZURE_AD_CLIENT_SECRET")
    
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

# Authentication Routes
@app.get("/auth/login", response_model=AuthURL)
async def login():
    """Initiate OAuth login flow"""
    try:
        auth_url, state = msal_auth.get_auth_url()
        return AuthURL(auth_url=auth_url, state=state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate auth URL: {str(e)}")

@app.get("/auth/callback")
async def auth_callback(code: str, state: str, error: Optional[str] = None):
    """Handle OAuth callback"""
    if error:
        # Redirect to frontend with error
        return RedirectResponse(url=f"http://localhost:3000/auth/callback?error={error}")
    
    if not code:
        return RedirectResponse(url="http://localhost:3000/auth/callback?error=missing_code")
    
    try:
        result = msal_auth.handle_callback(code, state)
        
        # Redirect to frontend with success data
        session_id = result["session_id"]
        return RedirectResponse(url=f"http://localhost:3000/auth/callback?session_id={session_id}&success=true")
        
    except HTTPException as e:
        logger.error(f"Callback HTTPException: {e.detail}")
        return RedirectResponse(url=f"http://localhost:3000/auth/callback?error={e.detail}")
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return RedirectResponse(url=f"http://localhost:3000/auth/callback?error=authentication_failed")

@app.get("/auth/session/{session_id}")
async def get_session_data(session_id: str):
    """Get session data for frontend"""
    session = msal_auth.verify_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    return {
        "success": True,
        "session_id": session_id,
        "user": session["user_info"],
        "expires_at": session["expires_at"].isoformat()
    }

@app.get("/auth/user", response_model=UserInfo)
async def get_user_info(user: Dict = Depends(require_unc_email)):
    """Get current user information"""
    return UserInfo(**user)

@app.post("/auth/logout")
async def logout(request: Request):
    """Logout current user"""
    # Extract session ID from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=400, detail="No session to logout")
    
    session_id = auth_header.split(" ")[1]
    success = msal_auth.logout(session_id)
    
    return {"success": success, "message": "Logged out successfully" if success else "No active session"}

@app.get("/auth/status")
async def auth_status(user: Optional[Dict] = Depends(get_optional_user)):
    """Check authentication status"""
    if user:
        return {
            "authenticated": True,
            "user": user
        }
    else:
        return {
            "authenticated": False,
            "user": None
        }

# Protected Routes
@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest, user: Dict = Depends(require_unc_email)):
    """
    Query the agent
    """
    conversation_id = request.conversation_id

    try:
        project_client = app.state.project_client
    except Exception:
        raise HTTPException(status_code=500, detail="Project client not initialized. Check server startup logs and environment variables.")

    try:
        agent = get_agent(project_client)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")
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


# EDI-specific endpoints
@app.post("/api/edi/query", response_model=EDIResponse)
async def query_edi_transactions(query: EDIQuery, user: Dict = Depends(require_unc_email)):
    """Main endpoint for EDI transaction queries"""
    
    try:
        logger.info(f"EDI query received: {query.question}")
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
        
        # Generate RAG response using LLM
        ai_answer = edi_search.generate_rag_response(query.question, transactions, params)
        
        return EDIResponse(
            answer=ai_answer,
            transactions=transaction_results,
            query_type=params["query_type"],
            search_performed=True
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing EDI query: {str(e)}")



@app.get("/api/edi/stats")
async def get_edi_statistics():
    """Get statistics about the EDI transaction database"""
    
    if not edi_search.search_client:
        raise HTTPException(status_code=503, detail="EDI search service not available")
    
    try:
        # Get total count
        count_result = edi_search.search_client.search(
            search_text="*",
            include_total_count=True,
            top=0
        )
        
        total_count = count_result.get_count()
        
        return {
            "total_transactions": total_count,
            "service_status": "active",
            "index_name": os.getenv("AZURE_SEARCH_INDEX_NAME", "edi-transactions")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting statistics: {str(e)}")


@app.post("/api/edi/search/amount")
async def search_by_amount(amount: float, date: Optional[str] = None):
    """Direct search by amount and optional date"""
    
    if not edi_search.search_client:
        raise HTTPException(status_code=503, detail="EDI search service not available")
    
    try:
        if date:
            filter_expr = f"amount eq {amount} and effective_date eq '{date}'"
        else:
            filter_expr = f"amount eq {amount}"
            
        results = edi_search.search_client.search(
            search_text="",
            filter=filter_expr,
            select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
            top=20
        )
        
        return [dict(result) for result in results]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching by amount: {str(e)}")


# Enhanced query endpoint that handles both EDI queries and general AI chat
@app.post("/api/chat")
async def enhanced_chat(request: QueryRequest, user: Dict = Depends(require_unc_email)):
    """Enhanced chat endpoint that handles both EDI queries and general AI chat"""
    
    # Check if this is an EDI-related query
    edi_keywords = ['trace number', 'transaction', '$', 'amount', 'june', 'bcbs', 'payment']
    
    if any(keyword in request.query.lower() for keyword in edi_keywords):
        # Route to EDI search
        edi_query = EDIQuery(question=request.query)
        edi_response = await query_edi_transactions(edi_query)

        return {
            "response": edi_response.answer,
            "type": "edi_search",
            "transactions_found": len(edi_response.transactions),
            "data": edi_response.transactions,
            "conversation_id": request.conversation_id or "edi_search"
        }
    else:
        # Route to existing AI agent
        ai_response = await query(request)
        print(f"AI response: {ai_response}")
        return {
            "response": ai_response["answer"],
            "type": "general_ai",
            "sources": ai_response["sources"],
            "conversation_id": ai_response["conversation_id"]
        }


@app.post("/api/edi-preprocess")
async def edi_preprocess(request: Request):
    """Connect to Azure Blob Storage, then run the edi_preprocessor.py script to preprocess the EDI transactions in the blob storage"""

    # Connect to Azure Blob Storage
    blob_service_client = AzureBlobContainerClient(os.getenv("AZURE_STORAGE_CONNECTION_STRING"), os.getenv("AZURE_STORAGE_CONTAINER_NAME"))
    container_client = blob_service_client.get_container_client(os.getenv("AZURE_STORAGE_CONTAINER_NAME"))

    # Run the edi_preprocessor.py script to preprocess the EDI transactions in the blob storage
    edi_preprocessor = EDIProcessor()
    edi_preprocessor.preprocess_edi_transactions()


    return {
        "message": "EDI transactions preprocessed"
    }


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

        logger.info(f"File uploaded successfully: {blob_name} by user {user.get('email', 'unknown')}")

        return {
            "success": True,
            "message": "File uploaded successfully",
            "filename": file.filename,
            "blob_name": blob_name,
            "size": len(file_content),
            "uploaded_by": user.get('email')
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
        logger.info(f"Starting incremental search index update requested by {user.get('email', 'unknown')}")

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
                "updated_by": user.get('email')
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


@app.get("/api/search-index-status")
async def get_search_index_status(user: Dict = Depends(require_unc_email)):
    """Get current search index status and information about new files"""

    try:
        updater = IncrementalIndexUpdater()

        # Find new files without processing them
        new_files, registry = updater.find_new_and_updated_files()

        # Get search index statistics
        search_service = updater.get_search_service()
        search_stats = search_service.get_statistics()

        return {
            "success": True,
            "search_index": {
                "total_transactions": search_stats.get("total_transactions", 0),
                "earliest_date": search_stats.get("earliest_date"),
                "latest_date": search_stats.get("latest_date"),
                "index_name": search_stats.get("index_name")
            },
            "pending_updates": {
                "new_files_count": len(new_files),
                "new_files": new_files[:10] if new_files else [],  # Show first 10 files
                "has_more": len(new_files) > 10
            },
            "last_registry_info": {
                "total_processed_files": len(registry),
                "last_update": max([info.processed_at for info in registry.values()]) if registry else None
            }
        }

    except Exception as e:
        logger.error(f"Error getting search index status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get search index status: {str(e)}"
        )


if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["**/networkx/**"]
    )