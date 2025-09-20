from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header
from ...services import document_parser, scoring_engine
from ...schemas.models import AnalysisResponse
import uuid

router = APIRouter()

@router.post("/analyze/", response_model=AnalysisResponse)
async def analyze_resume(
    jd: str = Form(...),
    resume: UploadFile = File(...),
    api_key: str = Header(..., alias="X-API-Key"),
    llm_model: str = Header(..., alias="X-LLM-Model")
):
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key is required.")
    
    if not resume.filename or not resume.filename.lower().endswith(('.pdf', '.docx')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PDF or DOCX.")

    try:
        resume_bytes = await resume.read()
        resume_text = document_parser.parse_document(resume.filename, resume_bytes)
        
        if not resume_text.strip():
            raise HTTPException(status_code=500, detail=f"Could not extract text from resume: {resume.filename}")
        
        # 1. Hard Match Scoring
        hard_score = scoring_engine.hard_match_score(resume_text, jd)

        # 2. LLM-based Semantic Analysis
        llm_results = scoring_engine.llm_analysis(resume_text, jd, api_key, llm_model)

        # 3. Final Scoring and Verdict
        final_score, verdict = scoring_engine.calculate_final_score_and_verdict(
            hard_score, llm_results["semantic_score"]
        )
        
        # Optional: Add the processed resume to the vector store for future search
        doc_id = str(uuid.uuid4())
        metadata = {"filename": resume.filename, "score": final_score, "verdict": verdict}
        scoring_engine.vector_store.add_document(doc_id, resume_text, metadata)

        return AnalysisResponse(
            relevance_score=final_score,
            verdict=verdict,
            missing_elements=llm_results["missing_elements"],
            improvement_suggestions=llm_results["improvement_suggestions"],
            filename=resume.filename
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")