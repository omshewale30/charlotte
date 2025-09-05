from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
    messages: Optional[List[Message]] = []

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
                azure_endpoint="https://charlotte-resource.cognitiveservices.azure.com/",
            )
            
            # Prompt for parameter extraction
            system_prompt = """You are an expert at extracting structured data from natural language queries about financial transactions.

Extract the following information from the user's query and return it as valid JSON:
- amount: float or null (monetary amount like $92.39, 103.12 dollars, etc.)
- date: string in YYYY-MM-DD format or null (dates like "June 2, 2025", "2nd June 2025", "6/2/2025", etc.)
- trace_number: string or null (specific transaction identifier - only if user provides one, NOT if they're asking for it)
- originator: string or null (company names like BCBS, Blue Cross, United Healthcare, etc.)
- query_type: string (one of: "amount_search", "trace_search", "originator_search", "date_search", "general")

Query type rules:
- If user asks "what is the trace number FOR" something, use amount_search/date_search, NOT trace_search
- Use trace_search only when user provides a specific trace number to look up
- Use amount_search when amount and date are both provided
- Use date_search when only date is provided
- Use originator_search when searching by company name

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
            
            # Parse JSON response
            params = json.loads(ai_response)
            
            # Validate and set defaults
            default_params = {
                "amount": None,
                "date": None,
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
                "date": None,
                "trace_number": None,
                "originator": None,
                "query_type": "general"
            }
    
    def search_transactions(self, params: Dict) -> List[Dict]:
        """Search for transactions based on extracted parameters"""
        if not self.search_client:
            logger.warning("Search client not available")
            return []
        
        logger.info(f"Searching with params: {params}")
        
        try:
            if params["query_type"] == "amount_search" and params["amount"] and params["date"]:
                # Exact amount and date search
                filter_expr = f"amount eq {params['amount']} and effective_date eq '{params['date']}'"
                logger.info(f"Using filter expression: {filter_expr}")
                
                results = self.search_client.search(
                    search_text="",
                    filter=filter_expr,
                    select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                    top=10
                )
                
                # Convert results to list and log
                result_list = [dict(result) for result in results]
                logger.info(f"Search returned {len(result_list)} results: {result_list}")
                return result_list
                
            elif params["query_type"] == "trace_search" and params["trace_number"]:
                # Trace number search
                filter_expr = f"trace_number eq '{params['trace_number']}'"
                logger.info(f"Using trace filter expression: {filter_expr}")
                results = self.search_client.search(
                    search_text="",
                    filter=filter_expr,
                    select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                    top=1
                )
                
            elif params["query_type"] == "originator_search" and params["originator"]:
                # Originator search
                logger.info(f"Searching originator: {params['originator']}")
                results = self.search_client.search(
                    search_text=params["originator"],
                    search_fields=["originator"],
                    select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                    top=20
                )
                
            elif params["amount"]:
                # Amount only search
                filter_expr = f"amount eq {params['amount']}"
                logger.info(f"Using amount filter expression: {filter_expr}")
                results = self.search_client.search(
                    search_text="",
                    filter=filter_expr,
                    select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                    top=10
                )
                
            elif params["date"]:
                # Date only search
                filter_expr = f"effective_date eq '{params['date']}'"
                logger.info(f"Using date filter expression: {filter_expr}")
                results = self.search_client.search(
                    search_text="",
                    filter=filter_expr,
                    select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                    top=50
                )
                
            else:
                logger.info("No matching search criteria found")
                return []
            
            # Convert results to list for non-amount_search queries
            if params["query_type"] != "amount_search":
                result_list = [dict(result) for result in results]
                logger.info(f"Search returned {len(result_list)} results")
                return result_list
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def format_ai_response(self, question: str, transactions: List[Dict], params: Dict) -> str:
        """Generate AI response based on search results"""
        if not transactions:
            return f"I couldn't find any transactions matching your query. Please check the amount, date, or other details and try again."
        
        # For specific amount + date queries
        if params["amount"] and params["date"] and len(transactions) == 1:
            t = transactions[0]
            return f"The trace number for the ${t['amount']} transaction on {t['effective_date']} is {t['trace_number']}. This transaction was from {t['originator']} to {t['receiver']}."
        
        # For trace number queries
        elif params["trace_number"] and len(transactions) == 1:
            t = transactions[0]
            return f"Trace number {t['trace_number']} corresponds to a ${t['amount']} transaction on {t['effective_date']} from {t['originator']} to {t['receiver']}."
        
        # For multiple results
        elif len(transactions) > 1:
            if params["amount"]:
                return f"I found {len(transactions)} transactions for ${params['amount']}. The trace numbers are: {', '.join([t['trace_number'] for t in transactions[:5]])}{'...' if len(transactions) > 5 else ''}."
            elif params["date"]:
                total_amount = sum(t['amount'] for t in transactions)
                return f"I found {len(transactions)} transactions on {params['date']} totaling ${total_amount:,.2f}. Would you like me to show specific details?"
            else:
                return f"I found {len(transactions)} matching transactions. Please provide more specific criteria to narrow down the results."
        
        return "I found some transactions but couldn't determine the best way to present the results."


# Initialize the EDI search integration
edi_search = EDISearchIntegration()


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


# EDI-specific endpoints
@app.post("/api/edi/query", response_model=EDIResponse)
async def query_edi_transactions(query: EDIQuery):
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
        
        # Generate AI response
        ai_answer = edi_search.format_ai_response(query.question, transactions, params)
        
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
async def enhanced_chat(request: QueryRequest):
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
        return {
            "response": ai_response.answer,
            "type": "general_ai",
            "sources": ai_response.sources,
            "conversation_id": ai_response.conversation_id
        }


if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["**/networkx/**"]
    )