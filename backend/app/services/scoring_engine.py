import spacy
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.schema.output_parser import StrOutputParser
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from fuzzywuzzy import fuzz

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading 'en_core_web_sm' model...")
    from spacy.cli import download
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def hard_match_score(resume_text: str, jd_text: str) -> float:
    """Calculates a score based on keyword matching."""
    try:
        # 1. TF-IDF Cosine Similarity
        vectorizer = TfidfVectorizer().fit_transform([resume_text, jd_text])
        vectors = vectorizer.toarray()
        tfidf_similarity = cosine_similarity(vectors)[0, 1]

        # 2. Fuzzy Match for key skills (example)
        jd_skills = ["python", "fastapi", "machine learning", "docker", "react", "aws", "sql"]
        resume_lower = resume_text.lower()
        fuzzy_score = sum(fuzz.partial_ratio(skill, resume_lower) > 80 for skill in jd_skills)
        fuzzy_normalized = (fuzzy_score / len(jd_skills)) if jd_skills else 0
        
        final_score = (tfidf_similarity * 0.7) + (fuzzy_normalized * 0.3)
        return min(final_score * 100, 100.0)
    except Exception as e:
        print(f"Error in hard_match_score: {e}")
        return 0.0


def llm_analysis(resume_text: str, jd_text: str, api_key: str, llm_model: str):
    """Uses an LLM to perform semantic analysis, gap identification, and feedback generation."""
    try:
        llm = ChatGoogleGenerativeAI(model=llm_model, google_api_key=api_key, temperature=0.2)
        
        template = """
        You are an expert AI recruitment assistant. Your task is to analyze a resume against a job description.
        Provide a detailed analysis in the following structured format. Do not include any other text, greetings, or explanations.

        **SEMANTIC_SCORE:** [Provide a score from 0 to 100 representing the semantic similarity and contextual fit. Base this on experience, project relevance, and overall alignment, not just keywords.]

        **MISSING_ELEMENTS:** [List the key skills, qualifications, or experiences mentioned in the job description that are missing from the resume. Be specific and use bullet points.]

        **IMPROVEMENT_SUGGESTIONS:** [Offer personalized, actionable feedback for the candidate to improve their resume for this specific role. Use bullet points.]

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
        
        # Parse the structured response
        semantic_score_str = response.split("**SEMANTIC_SCORE:**")[1].split("**MISSING_ELEMENTS:**")[0].strip()
        missing_elements = response.split("**MISSING_ELEMENTS:**")[1].split("**IMPROVEMENT_SUGGESTIONS:**")[0].strip()
        improvement_suggestions = response.split("**IMPROVEMENT_SUGGESTIONS:**")[1].strip()

        return {
            "semantic_score": float(semantic_score_str),
            "missing_elements": missing_elements,
            "improvement_suggestions": improvement_suggestions
        }
    except Exception as e:
        print(f"Error during LLM analysis: {e}")
        return {
            "semantic_score": 0.0,
            "missing_elements": "Error during LLM analysis. Please check the API key and model availability.",
            "improvement_suggestions": "Could not generate suggestions due to an error."
        }


def calculate_final_score_and_verdict(hard_score: float, semantic_score: float):
    """Calculates the final weighted score and provides a verdict."""
    # Weights can be tuned (e.g., 40% hard match, 60% semantic match)
    final_score = (hard_score * 0.4) + (semantic_score * 0.6)
    
    verdict = "Low"
    if final_score >= 80:
        verdict = "High"
    elif final_score >= 60:
        verdict = "Medium"
        
    return round(final_score, 2), verdict