import os
from typing import List, Dict
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import logging
from openai import AzureOpenAI
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
from azure.identity import ClientSecretCredential
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from conversation_memory import ConversationMemory
from conversation_memory import UnifiedConversationMemory
from fastapi import FastAPI

import json


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# EDI Search Service Integration
class EDISearchIntegration:
    """Integration class for EDI search in Charlotte"""
    
    def __init__(self, unified_memory: UnifiedConversationMemory, conversation_memory: ConversationMemory, project_client=None):
        self.unified_memory = unified_memory
        self.conversation_memory = conversation_memory
        self.project_client = project_client
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
            
            # The ** unpacks the search_params dictionary into keyword arguments
            # For example, if search_params = {"search_text": "foo", "top": 10}
            # This is equivalent to: search_client.search(search_text="foo", top=10)
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
                edi_context = self.conversation_memory.get_relevant_context(conversation_id, question)
                
                # Get Azure AI Foundry context if available
                azure_context = ""
                if conversation_id in self.unified_memory.session_threads:
                    try:
                        # Get recent Azure thread messages for context
                        # Note: project_client should be passed from the endpoint or accessed via dependency injection
                        # For now, we'll skip this if project_client is not available
                        if hasattr(self, 'project_client') and self.project_client:
                            thread = self.unified_memory.session_threads[conversation_id]
                            messages = self.project_client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.DESCENDING, top=5)
                        else:
                            messages = []
                        
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
