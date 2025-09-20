from sqlalchemy.orm import Session
from sqlalchemy import or_
from . import models
from ..schemas import models as schemas

def create_job_description(db: Session, jd: schemas.JobDescriptionCreate):
    db_jd = models.JobDescription(title=jd.title, description=jd.description)
    db.add(db_jd)
    db.commit()
    db.refresh(db_jd)
    return db_jd

def get_job_descriptions(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.JobDescription).offset(skip).limit(limit).all()

def get_job_description(db: Session, jd_id: int):
    return db.query(models.JobDescription).filter(models.JobDescription.id == jd_id).first()

def create_analysis_result(db: Session, result: schemas.AnalysisResultCreate, jd_id: int):
    db_result = models.AnalysisResult(**result.dict(), job_description_id=jd_id)
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result

def get_analysis_results_for_jd(db: Session, jd_id: int, search: str | None = None):
    query = db.query(models.AnalysisResult).filter(models.AnalysisResult.job_description_id == jd_id)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                models.AnalysisResult.filename.ilike(search_term),
                models.AnalysisResult.missing_elements.ilike(search_term),
                models.AnalysisResult.improvement_suggestions.ilike(search_term)
            )
        )
    return query.all()

def get_analysis_result(db: Session, result_id: int):
    return db.query(models.AnalysisResult).filter(models.AnalysisResult.id == result_id).first()

def update_analysis_result_status(db: Session, result_id: int, status: str):
    db_result = get_analysis_result(db, result_id)
    if db_result:
        db_result.status = status
        db.commit()
        db.refresh(db_result)
    return db_result