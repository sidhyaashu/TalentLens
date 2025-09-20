from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...database import crud
from ...database.database import get_db
from ...schemas import models as schemas
from ...services import notification_service
import logging

router = APIRouter()

@router.put("/results/{result_id}/status", response_model=schemas.AnalysisResult)
def update_status(result_id: int, status_update: schemas.StatusUpdate, db: Session = Depends(get_db)):
    updated_result = crud.update_analysis_result_status(db, result_id, status_update.status)
    if not updated_result:
        raise HTTPException(status_code=404, detail="Analysis result not found")
    return updated_result

@router.post("/results/{result_id}/send-feedback", status_code=202)
async def send_feedback_email(result_id: int, db: Session = Depends(get_db)):
    """
    Triggers the feedback webhook for a specific analysis result.
    """
    result = crud.get_analysis_result(db, result_id=result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis result not found")

    if not result.student_email:
        raise HTTPException(status_code=400, detail="No email found for this candidate, cannot send feedback.")

    # Convert the SQLAlchemy model to a Pydantic model, then to a dict
    analysis_data = schemas.AnalysisResult.from_orm(result).model_dump()

    try:
        await notification_service.send_feedback_webhook(
            email=result.student_email,
            analysis_data=analysis_data
        )
        return {"message": "Feedback sending process initiated."}
    except Exception as e:
        logging.error(f"Failed to send webhook for result {result_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send feedback.")