from pydantic import BaseModel, Field
from typing import List, Optional

# --- Analysis Schemas ---
class AnalysisResponse(BaseModel):
    relevance_score: float
    verdict: str
    missing_elements: str
    improvement_suggestions: str
    filename: str
    status: str = "New"

class AnalysisResultCreate(AnalysisResponse):
    pass

class AnalysisResult(AnalysisResponse):
    id: int
    job_description_id: int

    class Config:
        orm_mode = True

# --- Status Update Schema ---
class StatusUpdate(BaseModel):
    status: str

# --- Job Description Schemas ---
class JobDescriptionBase(BaseModel):
    title: str
    description: str

class JobDescriptionCreate(JobDescriptionBase):
    pass

class JobDescription(JobDescriptionBase):
    id: int
    analyses: List[AnalysisResult] = []

    class Config:
        orm_mode = True