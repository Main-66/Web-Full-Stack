import json
import httpx
from datetime import datetime, timedelta
from app.config import settings
from app.schemas import NLPParsedOutput

async def parse_natural_language_command(user_prompt: str) -> NLPParsedOutput:
    now = datetime.now().replace(second=0, microsecond=0)
    system_prompt = (
        f"You are a calendar scheduling parser. Current reference time is {now.isoformat()} ({now.strftime('%A')}). "
        "Convert the user's natural language command into a structured JSON object matching the exact schema. "
        "Calculate exact ISO 8601 dates (YYYY-MM-DDTHH:MM:SS) relative to the current reference time."
    )

    schema = NLPParsedOutput.model_json_schema()

    try:
        if settings.LLM_PROVIDER == "ollama":
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "format": schema,
                        "stream": False,
                        "options": {"temperature": 0.1}
                    }
                )
                response.raise_for_status()
                raw_json = response.json()["message"]["content"]
                return NLPParsedOutput.model_validate_json(raw_json)
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.CLOUD_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.CLOUD_API_KEY}"},
                    json={
                        "model": settings.CLOUD_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.1
                    }
                )
                response.raise_for_status()
                raw_json = response.json()["choices"][0]["message"]["content"]
                return NLPParsedOutput.model_validate_json(raw_json)

    except Exception as e:
        # Safe fallback if Ollama isn't running yet during initial UI testing
        fallback_start = (now + timedelta(hours=1)).replace(minute=0)
        fallback_end = fallback_start + timedelta(hours=2)
        return NLPParsedOutput(
            intent_type="schedule",
            title=f"{user_prompt} (Offline Fallback)",
            event_type="study",
            priority="medium",
            start_time=fallback_start.isoformat(),
            end_time=fallback_end.isoformat(),
            estimated_hours=2.0
        )