from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class JobDescription(Base):
    __tablename__ = "job_descriptions"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    analyses = relationship("AnalysisResult", back_populates="job_description")

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    relevance_score = Column(Float)
    verdict = Column(String)
    missing_elements = Column(Text)
    improvement_suggestions = Column(Text)
    student_email = Column(String, nullable=True)
    status = Column(String, default="New", index=True) # <-- ADD THIS LINE
    job_description_id = Column(Integer, ForeignKey("job_descriptions.id"))
    job_description = relationship("JobDescription", back_populates="analyses")