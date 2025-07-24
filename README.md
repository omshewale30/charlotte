# UNC RAG Chatbot Demo

A demonstration of Retrieval Augmented Generation (RAG) for answering questions about UNC Cashier Office procedures.

## Project Overview

This demo showcases a chatbot that can answer questions based on pre-existing .docx instruction manuals. The system uses:

- **Frontend**: Next.js with Tailwind CSS and shadcn/ui
- **Backend**: FastAPI (Python)
- **Vector Database**: ChromaDB (local persistence)
- **LLM & Embeddings**: OpenAI (GPT-4o-mini for chat, text-embedding-3-small for embeddings)
- **Document Processing**: Langchain

## Setup Instructions

### Prerequisites

- Node.js 18+ for the frontend
- Python 3.9+ for the backend
- OpenAI API key

### Environment Setup

1. Create a `.env` file in the project root with your OpenAI API key:

```
OPENAI_API_KEY=your_openai_api_key_here
```

### Sample Documents

1. Place 1-2 sample .docx instruction manuals in the `backend/documents/` directory.

### Frontend Setup

1. Install dependencies:

```bash
npm install
```

2. Run the development server:

```bash
npm run dev
```

### Backend Setup

1. Navigate to the backend directory:

```bash
cd backend
```

2. Create a Python virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install required packages:

```bash
pip install -r requirements.txt
```

4. Start the FastAPI server:

```bash
python app/main.py
```

## Usage

1. Open a web browser and navigate to http://localhost:3000
2. Type a question about Cashier Office procedures in the chat input
3. The system will retrieve relevant information from the documents and generate a response
4. Sources will be displayed with the response

## Features

- Document processing and embedding on application startup
- Semantic search for retrieving relevant document chunks
- LLM-powered question answering with source attribution
- Clean, professional UI with responsive design

## Architecture

- **Document Processing**: Documents are loaded, chunked, and embedded when the backend starts
- **Vector Storage**: Document chunks and their embeddings are stored in ChromaDB
- **Query Processing**: User questions are embedded and used to retrieve relevant document chunks
- **Response Generation**: Retrieved chunks are sent to the LLM with the user's question to generate a response

## Limitations

- This demo has a fixed set of documents and does not support document uploads
- The system is optimized for a specific domain (Cashier Office procedures)
- ChromaDB is used in local persistence mode and is not suitable for production-scale deployments

## Future Enhancements

- Document upload functionality
- User authentication and role-based access
- More sophisticated document processing (e.g., table extraction, image processing)
- Integration with university systems
- Enhanced conversation history and context management