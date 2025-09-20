import fitz  # PyMuPDF
from docx import Document
import io
import logging

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts text content from a PDF file."""
    try:
        pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            text += page.get_text()
        return text
    except Exception as e:
        logging.error(f"Error parsing PDF: {e}", exc_info=True)
        return ""

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extracts text content from a DOCX file."""
    try:
        document = Document(io.BytesIO(file_bytes))
        text = "\n".join([para.text for para in document.paragraphs])
        return text
    except Exception as e:
        logging.error(f"Error parsing DOCX: {e}", exc_info=True)
        return ""

def parse_document(file_name: str, file_bytes: bytes) -> str:
    """Parses a document based on its file extension."""
    if file_name.lower().endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif file_name.lower().endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    else:
        raise ValueError("Unsupported file format. Please upload a PDF or DOCX file.")