from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from ...services import document_parser, scoring_engine, notification_service
from ...services import vector_store as vs
from ...schemas.models import AnalysisResponse, AnalysisResultCreate
from ...database import crud
from ...database.database import get_db
import uuid
import logging
import asyncio

router = APIRouter()

def perform_analysis_and_save(
    db: Session,
    jd_text: str,
    resume_bytes: bytes,
    resume_filename: str,
    api_key: str,
    llm_model: str,
    jd_id: int
):
    try:
        resume_text = document_parser.parse_document(resume_filename, resume_bytes)
        if not resume_text.strip():
            logging.error(f"Could not extract text from resume: {resume_filename}")
            return

        hard_score = scoring_engine.hard_match_score(resume_text, jd_text)
        llm_results = scoring_engine.llm_analysis(resume_text, jd_text, api_key, llm_model)
        final_score, verdict = scoring_engine.calculate_final_score_and_verdict(
            hard_score, llm_results["semantic_score"]
        )

        analysis_data = AnalysisResultCreate(
            relevance_score=final_score,
            verdict=verdict,
            missing_elements=llm_results["missing_elements"],
            improvement_suggestions=llm_results["improvement_suggestions"],
            filename=resume_filename
        )

        crud.create_analysis_result(db=db, result=analysis_data, jd_id=jd_id)

        doc_id = str(uuid.uuid4())
        metadata = {"filename": resume_filename, "score": final_score, "verdict": verdict, "jd_id": jd_id}
        vs.vector_store.add_document(doc_id, resume_text, metadata)

        # Send feedback webhook
        student_email = scoring_engine.extract_email_from_text(resume_text)
        if student_email:
            # notification_service.send_feedback_webhook(student_email, analysis_data.dict())
            asyncio.run(notification_service.send_feedback_webhook(student_email, analysis_data.model_dump()))

    except Exception as e:
        logging.error(f"Background analysis failed for {resume_filename}: {e}", exc_info=True)


@router.post("/analyze/")
async def analyze_resume(
    background_tasks: BackgroundTasks,
    jd_id: int = Form(...),
    resume: UploadFile = File(...),
    api_key: str = Header(..., alias="X-API-Key"),
    llm_model: str = Header(..., alias="X-LLM-Model"),
    db: Session = Depends(get_db)
):
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key is required.")

    jd_model = crud.get_job_description(db=db, jd_id=jd_id)
    if not jd_model:
        raise HTTPException(status_code=404, detail="Job Description not found.")

    if not resume.filename or not resume.filename.lower().endswith(('.pdf', '.docx')):
        raise HTTPException(status_code=400, detail="Invalid file type.")

    resume_bytes = await resume.read()

    background_tasks.add_task(
        perform_analysis_and_save,
        db, jd_model.description, resume_bytes, resume.filename, api_key, llm_model, jd_id
    )

    return {"message": "Analysis started in the background for " + resume.filename}