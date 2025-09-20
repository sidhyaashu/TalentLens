from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...database import crud
from ...database.database import get_db
from ...schemas import models as schemas

router = APIRouter()

@router.put("/results/{result_id}/status", response_model=schemas.AnalysisResult)
def update_status(result_id: int, status_update: schemas.StatusUpdate, db: Session = Depends(get_db)):
    updated_result = crud.update_analysis_result_status(db, result_id, status_update.status)
    if not updated_result:
        raise HTTPException(status_code=404, detail="Analysis result not found")
    return updated_result