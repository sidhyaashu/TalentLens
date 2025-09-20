from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import crud, models
from ...database.database import get_db
from ...schemas import models as schemas

router = APIRouter()

@router.post("/jobs/", response_model=schemas.JobDescription)
def create_job_description(jd: schemas.JobDescriptionCreate, db: Session = Depends(get_db)):
    return crud.create_job_description(db=db, jd=jd)

@router.get("/jobs/", response_model=List[schemas.JobDescription])
def read_job_descriptions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    jds = crud.get_job_descriptions(db, skip=skip, limit=limit)
    return jds

@router.get("/jobs/{jd_id}/results", response_model=List[schemas.AnalysisResult])
def read_analysis_results_for_jd(
    jd_id: int,
    search: Optional[str] = Query(None, alias="search"),
    db: Session = Depends(get_db)
):
    results = crud.get_analysis_results_for_jd(db=db, jd_id=jd_id, search=search)
    return results