import httpx
import logging
from ..core.config import settings

async def send_feedback_webhook(email: str, analysis_data: dict):
    if not settings.N8N_WEBHOOK_URL:
        logging.warning("N8N_WEBHOOK_URL is not set. Skipping notification.")
        return

    payload = {
        "email": email,
        "filename": analysis_data.get("filename"),
        "score": analysis_data.get("relevance_score"),
        "verdict": analysis_data.get("verdict"),
        "missing": analysis_data.get("missing_elements"),
        "suggestions": analysis_data.get("improvement_suggestions")
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(settings.N8N_WEBHOOK_URL, json=payload)
            response.raise_for_status()
            logging.info(f"Successfully sent webhook for {email}")
    except httpx.RequestError as e:
        logging.error(f"Error sending webhook to n8n: {e}")