from fastapi import FastAPI
from .api.endpoints import analysis,jobs,results
from fastapi.middleware.cors import CORSMiddleware
from .database import models
from .database.database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Automated Resume Relevance Check System",
    description="An AI-powered system to evaluate resume relevance against job descriptions.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(jobs.router, prefix="/api", tags=["Job Descriptions"])
app.include_router(results.router, prefix="/api", tags=["Results"])

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Resume Analysis API is running."}