import spacy
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.schema.output_parser import StrOutputParser
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from fuzzywuzzy import fuzz
import re
import logging

# --- Lazy Loading for spaCy model ---
nlp_model = None

def get_spacy_model():
    """Loads and returns the spaCy model, downloading if necessary."""
    global nlp_model
    if nlp_model is None:
        try:
            nlp_model = spacy.load("en_core_web_sm")
        except OSError:
            logging.info("Downloading spaCy model 'en_core_web_sm'...")
            from spacy.cli import download
            download("en_core_web_sm")
            nlp_model = spacy.load("en_core_web_sm")
    return nlp_model
# ---

def hard_match_score(resume_text: str, jd_text: str) -> float:
    """Calculates a score based on keyword matching."""
    try:
        vectorizer = TfidfVectorizer().fit_transform([resume_text, jd_text])
        vectors = vectorizer.toarray()
        tfidf_similarity = cosine_similarity(vectors)[0, 1]

        jd_skills = ["python", "fastapi", "machine learning", "docker", "react", "aws", "sql"] # Example skills
        resume_lower = resume_text.lower()
        fuzzy_score = sum(fuzz.partial_ratio(skill, resume_lower) > 80 for skill in jd_skills)
        fuzzy_normalized = (fuzzy_score / len(jd_skills)) if jd_skills else 0
        
        final_score = (tfidf_similarity * 0.7) + (fuzzy_normalized * 0.3)
        return min(final_score * 100, 100.0)
    except Exception as e:
        logging.error(f"Error in hard_match_score: {e}", exc_info=True)
        return 0.0

def llm_analysis(resume_text: str, jd_text: str, api_key: str, llm_model: str):
    """Uses an LLM to perform semantic analysis, gap identification, and feedback generation."""
    try:
        llm = ChatGoogleGenerativeAI(model=llm_model, google_api_key=api_key, temperature=0.2)
        
        template = """
        You are an expert AI recruitment assistant. Your task is to analyze a resume against a job description.
        Provide a detailed analysis in the following structured format. Do not include any other text, greetings, or explanations.

        **SEMANTIC_SCORE:** [Provide a score from 0 to 100 representing the semantic similarity and contextual fit.]
        **MISSING_ELEMENTS:** [List the key skills, qualifications, or experiences from the JD that are missing from the resume.]
        **IMPROVEMENT_SUGGESTIONS:** [Offer actionable feedback for the candidate to improve their resume for this role.]

        ---
        JOB DESCRIPTION:
        {jd}
        ---
        RESUME:
        {resume}
        ---
        """
        
        prompt = PromptTemplate.from_template(template)
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({"jd": jd_text, "resume": resume_text})
        
        # Robustly parse the structured response using regex
        score_match = re.search(r"\*\*SEMANTIC_SCORE:\*\*\s*\[?(\d{1,3}(?:\.\d+)?)\]?", response)
        semantic_score = float(score_match.group(1)) if score_match else 0.0

        missing_match = re.search(r"\*\*MISSING_ELEMENTS:\*\*(.*?)\*\*IMPROVEMENT_SUGGESTIONS:\*\*", response, re.DOTALL)
        missing_elements = missing_match.group(1).strip() if missing_match else "Could not parse missing elements from the response."

        suggestions_match = re.search(r"\*\*IMPROVEMENT_SUGGESTIONS:\*\*(.*)", response, re.DOTALL)
        improvement_suggestions = suggestions_match.group(1).strip() if suggestions_match else "Could not parse improvement suggestions from the response."

        return {
            "semantic_score": semantic_score,
            "missing_elements": missing_elements,
            "improvement_suggestions": improvement_suggestions
        }
    except Exception as e:
        logging.error(f"Error during LLM analysis: {e}", exc_info=True)
        return {
            "semantic_score": 0.0,
            "missing_elements": "An error occurred during LLM analysis. Please check the server logs and API key.",
            "improvement_suggestions": "Could not generate suggestions due to an internal error."
        }

def calculate_final_score_and_verdict(hard_score: float, semantic_score: float) -> tuple[float, str]:
    """Calculates the final weighted score and provides a verdict."""
    final_score = (hard_score * 0.4) + (semantic_score * 0.6)
    
    verdict = "Low"
    if final_score >= 80:
        verdict = "High"
    elif final_score >= 60:
        verdict = "Medium"
        
    return round(final_score, 2), verdict