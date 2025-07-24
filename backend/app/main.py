from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
from typing import List, Dict, Optional, Any
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Langchain imports
from langchain_community.document_loaders import UnstructuredWordDocumentLoader, UnstructuredExcelLoader, CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langchain.memory import ConversationBufferMemory

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Check for OpenAI API key
if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY environment variable not set!")
    raise ValueError("OPENAI_API_KEY environment variable not set!")

# Initialize vector store on startup
vector_store = None

# Store conversation memories
conversation_memories: Dict[str, ConversationBufferMemory] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store
    vector_store = setup_vector_store()
    yield

# Initialize FastAPI app
app = FastAPI(title="UNC Chatbot Demo", lifespan=lifespan)

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

# Constants
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
COLLECTION_NAME = "unc_manuals_demo"
DOCUMENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "documents")
DEPARTMENT_ID = "cashier_office"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K_RESULTS = 4

# Setup vector store
def setup_vector_store():
    logger.info("Setting up vector store...")
    
    # Create documents directory if it doesn't exist
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    
    # Initialize OpenAI embeddings
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # Initialize ChromaDB
    db = Chroma(
        persist_directory=CHROMA_PERSIST_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME
    )
    
    # Check if collection is already populated
    if db._collection.count() > 0:
        logger.info(f"Collection '{COLLECTION_NAME}' already exists with {db._collection.count()} documents")
        return db
    
    logger.info("Collection is empty. Processing documents...")
    
    # Check for documents in the documents directory
    docx_files = [f for f in os.listdir(DOCUMENTS_DIR) if f.endswith('.docx')]
    xlsx_files = [f for f in os.listdir(DOCUMENTS_DIR) if f.endswith('.xlsx')]
    csv_files = [f for f in os.listdir(DOCUMENTS_DIR) if f.endswith('.csv')]
    
    if not docx_files and not xlsx_files and not csv_files:
        logger.warning(f"No .docx, .xlsx, or .csv files found in {DOCUMENTS_DIR}")
        return db
    
    # Process each document
    all_texts = []
    all_metadatas = []
    
    # Process Word documents
    for docx_file in docx_files:
        docx_path = os.path.join(DOCUMENTS_DIR, docx_file)
        logger.info(f"Processing Word document: {docx_file}")
        
        try:
            # Load document
            loader = UnstructuredWordDocumentLoader(docx_path)
            document = loader.load()
            
            # Split document into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP
            )
            chunks = text_splitter.split_documents(document)
            
            logger.info(f"Split {docx_file} into {len(chunks)} chunks")
            
            # Prepare texts and metadata for vector store
            for chunk in chunks:
                all_texts.append(chunk.page_content)
                all_metadatas.append({
                    "source_document_name": docx_file,
                    "text_chunk": chunk.page_content,
                    "department_id": DEPARTMENT_ID,
                    "file_type": "word"
                })
                
        except Exception as e:
            logger.error(f"Error processing {docx_file}: {str(e)}")
    
    
    
    if all_texts:
        # Add all documents to the vector store
        db.add_texts(texts=all_texts, metadatas=all_metadatas)
        logger.info(f"Added {len(all_texts)} chunks to vector store")
        
        # Persist the vector store

        logger.info("Vector store persisted successfully")
    
    return db

# Query endpoint
@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    if not vector_store:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    query_text = request.query.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    logger.info(f"Received query: {query_text}")
    
    try:
        # Get or create conversation memory
        conversation_id = request.conversation_id or str(uuid.uuid4())
        if conversation_id not in conversation_memories:
            conversation_memories[conversation_id] = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True
            )
        
        memory = conversation_memories[conversation_id]
        
        # Add previous messages to memory if provided
        if request.messages:
            for msg in request.messages:
                if msg.role == "user":
                    memory.chat_memory.add_user_message(msg.content)
                elif msg.role == "assistant":
                    memory.chat_memory.add_ai_message(msg.content)
        
        # Retrieve relevant documents
        retriever = vector_store.as_retriever(
            search_kwargs={
                "k": TOP_K_RESULTS,
                "filter": {"department_id": DEPARTMENT_ID}
            }
        )
        retrieved_docs = retriever.get_relevant_documents(query_text)
        
        if not retrieved_docs:
            logger.info("No relevant documents found")
            return QueryResponse(
                answer="I couldn't find any relevant information in the available documents to answer your question.",
                sources=[],
                conversation_id=conversation_id
            )
        
        # Create context from retrieved documents
        context = "\n\n".join([doc.page_content for doc in retrieved_docs])
        
        # Prepare sources for response
        sources = []
        seen_docs = set()
        for doc in retrieved_docs:
            doc_name = doc.metadata.get("source_document_name", "Unknown")
            if doc_name not in seen_docs:
                text_snippet = doc.page_content[:50] + "..." if len(doc.page_content) > 50 else doc.page_content
                sources.append(Source(document_name=doc_name, text_snippet=text_snippet))
                seen_docs.add(doc_name)
        
        # Create prompt for OpenAI with conversation history
        system_template = """You are a helpful AI assistant for UNC staff. Based only on the provided excerpts from internal procedural manuals, answer the user's question. If the information is not found in the excerpts, clearly state that the answer cannot be found in the provided documents. Do not make up information. If its a general question, answer it in a way that is helpful to the user.

Previous conversation:
{chat_history}

Excerpts:
{context}"""
        
        human_template = """User's Question: {query}"""
        
        chat = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        # Get conversation history
        chat_history = memory.load_memory_variables({})["chat_history"]
        
        messages = [
            SystemMessage(content=system_template.format(
                chat_history="\n".join([f"{msg.type}: {msg.content}" for msg in chat_history]),
                context=context
            )),
            HumanMessage(content=human_template.format(query=query_text))
        ]
        
        # Generate answer
        response = chat(messages)
        answer = response.content
        
        # Save to memory
        memory.chat_memory.add_user_message(query_text)
        memory.chat_memory.add_ai_message(answer)
        
        logger.info("Generated answer successfully")
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            conversation_id=conversation_id
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["**/networkx/**"]
    )