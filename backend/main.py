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
from auth import get_current_user, require_unc_email, get_optional_user
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

# Unified memory management system
class UnifiedConversationMemory:
    """Manages conversation memory for both Azure AI Foundry and EDI queries"""
    
    def __init__(self):
        # Azure AI Foundry thread management
        self.session_threads = {}
        # EDI conversation memory
        self.edi_memories = {}
        # Cross-system conversation tracking
        self.conversation_registry = {}
    
    def get_or_create_azure_thread(self, conversation_id: str, project_client):
        """Get or create Azure AI Foundry thread for a conversation"""
        if conversation_id not in self.session_threads:
            thread = project_client.agents.threads.create()
            self.session_threads[conversation_id] = thread
            # Register this conversation
            self._register_conversation(conversation_id, "azure_thread", thread.id)
        else:
            thread = project_client.agents.threads.get(self.session_threads[conversation_id].id)
        return thread
    
    def get_edi_conversation_history(self, conversation_id: str) -> List[Dict]:
        """Get EDI conversation history for a given conversation ID"""
        if conversation_id and conversation_id in self.edi_memories:
            return self.edi_memories[conversation_id]
        return []
    
    def add_edi_message(self, conversation_id: str, role: str, content: str, metadata: Dict = None):
        """Add a message to EDI conversation history"""
        if not conversation_id:
            return
            
        if conversation_id not in self.edi_memories:
            self.edi_memories[conversation_id] = []
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.edi_memories[conversation_id].append(message)
        
        # Keep only last 20 messages to prevent memory bloat
        if len(self.edi_memories[conversation_id]) > 20:
            self.edi_memories[conversation_id] = self.edi_memories[conversation_id][-20:]
        
        # Register this conversation if not already registered
        self._register_conversation(conversation_id, "edi_memory", None)
    
    def get_unified_context(self, conversation_id: str, current_query: str, max_messages: int = 5) -> str:
        """Get unified conversation context from both systems"""
        context_parts = []
        
        # Get EDI conversation history
        edi_history = self.get_edi_conversation_history(conversation_id)
        if edi_history:
            recent_edi = edi_history[-max_messages:] if len(edi_history) > max_messages else edi_history
            for msg in recent_edi:
                if msg["role"] == "user":
                    context_parts.append(f"User (EDI): {msg['content']}")
                elif msg["role"] == "assistant":
                    context_parts.append(f"Assistant (EDI): {msg['content']}")
        
        # Get Azure thread messages if available
        if conversation_id in self.session_threads:
            try:
                # This would require access to project_client, so we'll handle it in the calling function
                pass
            except:
                pass
        
        if context_parts:
            return "Previous conversation context:\n" + "\n".join(context_parts) + "\n\n"
        
        return ""
    
    def get_edi_relevant_context(self, conversation_id: str, current_query: str, max_messages: int = 5) -> str:
        """Get relevant context from EDI conversation history"""
        history = self.get_edi_conversation_history(conversation_id)
        
        if not history:
            return ""
        
        # Get recent messages (excluding the current one)
        recent_messages = history[-max_messages:] if len(history) > max_messages else history
        
        context_parts = []
        for msg in recent_messages:
            if msg["role"] == "user":
                context_parts.append(f"User: {msg['content']}")
            elif msg["role"] == "assistant":
                context_parts.append(f"Assistant: {msg['content']}")
        
        if context_parts:
            return "Previous conversation context:\n" + "\n".join(context_parts) + "\n\n"
        
        return ""
    
    def _register_conversation(self, conversation_id: str, system_type: str, thread_id: str = None):
        """Register a conversation in the cross-system registry"""
        if conversation_id not in self.conversation_registry:
            self.conversation_registry[conversation_id] = {
                "azure_thread_id": None,
                "edi_memory_active": False,
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat()
            }
        
        if system_type == "azure_thread":
            self.conversation_registry[conversation_id]["azure_thread_id"] = thread_id
        elif system_type == "edi_memory":
            self.conversation_registry[conversation_id]["edi_memory_active"] = True
        
        self.conversation_registry[conversation_id]["last_activity"] = datetime.now().isoformat()
    
    def get_conversation_info(self, conversation_id: str) -> Dict:
        """Get information about a conversation across both systems"""
        return self.conversation_registry.get(conversation_id, {})

# Initialize unified conversation memory
unified_memory = UnifiedConversationMemory()

# Legacy compatibility - keep the old conversation_memory for existing code
class ConversationMemory:
    """Legacy wrapper for backward compatibility"""
    
    def __init__(self, unified_memory):
        self.unified_memory = unified_memory
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        return self.unified_memory.get_edi_conversation_history(conversation_id)
    
    def add_message(self, conversation_id: str, role: str, content: str, metadata: Dict = None):
        self.unified_memory.add_edi_message(conversation_id, role, content, metadata)
    
    def get_relevant_context(self, conversation_id: str, current_query: str, max_messages: int = 5) -> str:
        return self.unified_memory.get_edi_relevant_context(conversation_id, current_query, max_messages)

# Initialize conversation memory for backward compatibility
conversation_memory = ConversationMemory(unified_memory)

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
    
    def generate_rag_response(self, question: str, transactions: List[Dict], params: Dict, conversation_id: str = None) -> str:
        """Generate RAG response by feeding transaction context to LLM with unified conversation memory"""
        try:
            # Setup OpenAI client
            openai_client = AzureOpenAI(
                api_version="2024-12-01-preview",
                api_key=os.getenv("AZURE_OPENAI_KEY"),
                azure_endpoint="https://charlotte-ai-resource.openai.azure.com/",
            )
            
            # Prepare context from transactions
            context = self.prepare_context(transactions)
            
            # Get unified conversation context if available
            conversation_context = ""
            if conversation_id:
                # Get EDI conversation context
                edi_context = conversation_memory.get_relevant_context(conversation_id, question)
                
                # Get Azure AI Foundry context if available
                azure_context = ""
                if conversation_id in unified_memory.session_threads:
                    try:
                        # Get recent Azure thread messages for context
                        project_client = app.state.project_client
                        thread = unified_memory.session_threads[conversation_id]
                        messages = project_client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.DESCENDING, top=5)
                        
                        azure_context_parts = []
                        for msg in messages:
                            if msg.role == "user":
                                azure_context_parts.append(f"User (General): {msg.content}")
                            elif msg.role == "assistant":
                                # Extract text content from assistant messages
                                if msg.content and isinstance(msg.content, list):
                                    for part in msg.content:
                                        if part.get("type") == "text" and "text" in part and "value" in part["text"]:
                                            azure_context_parts.append(f"Assistant (General): {part['text']['value']}")
                                            break
                        
                        if azure_context_parts:
                            azure_context = "Previous general conversation:\n" + "\n".join(azure_context_parts) + "\n\n"
                    except Exception as e:
                        logger.warning(f"Could not retrieve Azure context: {str(e)}")
                
                # Combine contexts
                if edi_context and azure_context:
                    conversation_context = f"{azure_context}{edi_context}"
                elif edi_context:
                    conversation_context = edi_context
                elif azure_context:
                    conversation_context = azure_context
            
            # Handle special cases
            if not transactions:
                return "I couldn't find any transactions matching your query. Please check the criteria and try again."
            
            # Handle count queries
            if len(transactions) == 1 and "total_count" in transactions[0]:
                count = transactions[0]["total_count"]
                return f"I have **{count:,}** EDI transactions in the database."
            
            # Create system prompt for RAG response with unified conversation context
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
- Consider the conversation context to provide more relevant and contextual responses
- Reference previous queries when relevant to provide continuity

{conversation_context}Transaction Data Context:
{context}

Answer the user's question based on this transaction data and conversation context."""

            user_prompt = f"User's question: {question}\n\nPlease analyze the transaction data and provide a comprehensive answer."
            
            response = openai_client.chat.completions.create(
                model=os.getenv("SMALL_MODEL_NAME", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt.format(
                        conversation_context=conversation_context,
                        context=context
                    )},
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
            agent = get_agent(project_client)
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


# EDI-specific endpoints
@app.post("/api/edi/query", response_model=EDIResponse)
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



@app.get("/api/edi/conversation/{conversation_id}")
async def get_conversation_history(conversation_id: str, user: Dict = Depends(require_unc_email)):
    """Get conversation history for a specific conversation ID"""
    
    try:
        history = conversation_memory.get_conversation_history(conversation_id)
        
        return {
            "conversation_id": conversation_id,
            "message_count": len(history),
            "messages": history,
            "retrieved_by": user.get('email') if user and isinstance(user, dict) else None
        }
        
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving conversation history: {str(e)}")


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
    """Enhanced chat endpoint that handles both EDI queries and general AI chat with unified memory"""
    
    # Ensure we have a conversation_id
    conversation_id = request.conversation_id
    if not conversation_id:
        user_email = user.get('email', 'anonymous') if user and isinstance(user, dict) else 'anonymous'
        conversation_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_email}"
    
    # Check if this is an EDI-related query
    edi_keywords = ['trace number', 'transaction', '$', 'amount', 'june', 'bcbs', 'payment']
    
    if any(keyword in request.query.lower() for keyword in edi_keywords):
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