from pydantic import BaseModel
from typing import List, Optional

# --- Analysis Schemas ---

class AnalysisResponse(BaseModel):
    """
    Base model for analysis data. Includes all core fields from an analysis.
    """
    relevance_score: float
    verdict: str
    missing_elements: str
    improvement_suggestions: str
    filename: str
    status: Optional[str] = "New"
    student_email: Optional[str] = None # Stores the candidate's email if found

class AnalysisResultCreate(AnalysisResponse):
    """
    Schema used when creating a new analysis result in the database.
    Inherits all fields from AnalysisResponse.
    """
    pass

class AnalysisResult(AnalysisResponse):
    """
    Schema for reading an analysis result from the database.
    Includes database-generated fields like 'id'.
    """
    id: int
    job_description_id: int

    class Config:
        from_attributes = True

# --- Status Update Schema ---

class StatusUpdate(BaseModel):
    """
    Schema for updating a candidate's status (e.g., "Shortlisted").
    """
    status: str

# --- Job Description Schemas ---

class JobDescriptionBase(BaseModel):
    """
    Base model for job description data.
    """
    title: str
    description: str

class JobDescriptionCreate(JobDescriptionBase):
    """
    Schema used when creating a new job description.
    """
    pass

class JobDescription(JobDescriptionBase):
    """
    Schema for reading a job description, including its related analyses.
    """
    id: int
    analyses: List[AnalysisResult] = [] # Will hold a list of associated candidates

    class Config:
        # Enable mapping from the JobDescription SQLAlchemy model.
        from_attributes = True