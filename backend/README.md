# Sample Documents Directory

Place your .docx instruction manuals in this directory. The RAG chatbot will load and process these documents on startup.

Example files might include:
- Running the Daily Cash Transmittal Report.docx
- Processing Student Refunds.docx

All documents will be processed, chunked, and embedded in the ChromaDB vector database.

Note: This is a demo system. In a production environment, you would implement proper document management with upload capabilities, version control, and scheduled re-indexing.