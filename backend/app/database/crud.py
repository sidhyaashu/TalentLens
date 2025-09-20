from sqlalchemy.orm import Session
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

def get_analysis_results_for_jd(db: Session, jd_id: int):
    return db.query(models.AnalysisResult).filter(models.AnalysisResult.job_description_id == jd_id).all()