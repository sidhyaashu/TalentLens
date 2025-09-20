from pydantic import BaseModel

class AnalysisResponse(BaseModel):
    relevance_score: float
    verdict: str
    missing_elements: str
    improvement_suggestions: str
    filename: str