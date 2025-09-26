"""
FastAPI integration for Charlotte system with EDI search capabilities
Add this to your existing FastAPI backend
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
import re
from datetime import datetime
import openai
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

# Pydantic models for API requests/responses
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
            print(f"Warning: Could not initialize Azure Search client: {e}")
    
    def extract_query_parameters(self, question: str) -> Dict:
        """Extract structured parameters from natural language query"""
        params = {
            "amount": None,
            "date": None,
            "trace_number": None,
            "originator": None,
            "query_type": "general"
        }
        
        # Extract amount patterns
        amount_patterns = [
            r'\$([0-9,]+\.?[0-9]*)',  # $103.12, $1,308.72
            r'([0-9,]+\.?[0-9]*)\s*dollars?',  # 103.12 dollars
            r'amount.*?([0-9,]+\.?[0-9]*)',  # amount of 103.12
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    params["amount"] = float(amount_str)
                    params["query_type"] = "amount_search"
                    break
                except ValueError:
                    continue
        
        # Extract date patterns
        date_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY
            r'(\d{4}-\d{1,2}-\d{1,2})',  # YYYY-MM-DD
            r'june\s+(\d{1,2}),?\s*(\d{4})',  # June 2, 2025
            r'(\d{1,2})\s+june\s+(\d{4})',  # 2 June 2025
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                if 'june' in pattern:
                    # Handle June date format
                    if len(match.groups()) == 2:
                        day, year = match.groups()
                        params["date"] = f"{year}-06-{day.zfill(2)}"
                else:
                    date_str = match.group(1)
                    # Convert MM/DD/YYYY to YYYY-MM-DD
                    if '/' in date_str:
                        try:
                            date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                            params["date"] = date_obj.strftime('%Y-%m-%d')
                        except ValueError:
                            continue
                    else:
                        params["date"] = date_str
                break
        
        # Extract trace number
        trace_patterns = [
            r'trace\s+number\s+([A-Za-z0-9]+)',
            r'trace\s+([A-Za-z0-9]+)',
            r'transaction\s+([A-Za-z0-9]+)'
        ]
        
        for pattern in trace_patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                params["trace_number"] = match.group(1)
                params["query_type"] = "trace_search"
                break
        
        # Extract originator/company names
        company_patterns = [
            r'(BCBS[-\s]?N?C?)',
            r'(Blue\s+Cross)',
            r'(United\s*Health\s*Care?)',
            r'(Cigna)',
            r'(Medica)'
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                params["originator"] = match.group(1)
                params["query_type"] = "originator_search"
                break
        
        return params
    
    def search_transactions(self, params: Dict) -> List[Dict]:
        """Search for transactions based on extracted parameters"""
        if not self.search_client:
            return []
        
        try:
            if params["query_type"] == "amount_search" and params["amount"] and params["date"]:
                # Exact amount and date search
                filter_expr = f"amount eq {params['amount']} and effective_date eq '{params['date']}'"
                results = self.search_client.search(
                    search_text="",
                    filter=filter_expr,
                    select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                    top=10
                )
                
            elif params["query_type"] == "trace_search" and params["trace_number"]:
                # Trace number search
                filter_expr = f"trace_number eq '{params['trace_number']}'"
                results = self.search_client.search(
                    search_text="",
                    filter=filter_expr,
                    select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                    top=1
                )
                
            elif params["query_type"] == "originator_search" and params["originator"]:
                # Originator search
                results = self.search_client.search(
                    search_text=params["originator"],
                    search_fields=["originator"],
                    select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                    top=20
                )
                
            elif params["amount"]:
                # Amount only search
                filter_expr = f"amount eq {params['amount']}"
                results = self.search_client.search(
                    search_text="",
                    filter=filter_expr,
                    select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                    top=10
                )
                
            elif params["date"]:
                # Date only search
                filter_expr = f"effective_date eq '{params['date']}'"
                results = self.search_client.search(
                    search_text="",
                    filter=filter_expr,
                    select=["trace_number", "amount", "effective_date", "originator", "receiver", "page_number"],
                    top=50
                )
                
            else:
                return []
            
            return [dict(result) for result in results]
            
        except Exception as e:
            print(f"Search error: {e}")
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

# FastAPI endpoints
app = FastAPI()

@app.post("/api/edi/query", response_model=EDIResponse)
async def query_edi_transactions(query: EDIQuery):
    """Main endpoint for EDI transaction queries"""
    
    try:
        # Extract parameters from natural language query
        params = edi_search.extract_query_parameters(query.question)
        
        # Search for matching transactions
        transactions = edi_search.search_transactions(params)
        
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

# Add this to your existing Charlotte FastAPI app
# Example of how to integrate with your existing chat endpoint:

@app.post("/api/chat")
async def enhanced_chat(message: str):
    """Enhanced chat endpoint that handles both EDI queries and general AI chat"""
    
    # Check if this is an EDI-related query
    edi_keywords = ['trace number', 'transaction', '$', 'amount', 'june', 'bcbs', 'payment']
    
    if any(keyword in message.lower() for keyword in edi_keywords):
        # Route to EDI search
        edi_query = EDIQuery(question=message)
        edi_response = await query_edi_transactions(edi_query)
        
        return {
            "response": edi_response.answer,
            "type": "edi_search",
            "transactions_found": len(edi_response.transactions),
            "data": edi_response.transactions
        }
    else:
        # Route to your existing AI agent
        # Your existing Charlotte AI logic here
        return {
            "response": "Your existing AI response",
            "type": "general_ai"
        }