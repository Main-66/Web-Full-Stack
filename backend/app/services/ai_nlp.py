import httpx
from datetime import datetime, timedelta
from app.config import settings
from app.schemas import NLPParsedOutput

def clean_json_text(text: str) -> str:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text

def validate_base_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        raise ValueError("Base URL must start with http:// or https://")
    return cleaned

async def parse_natural_language_command(
    user_prompt: str,
    api_key: str = None,
    base_url: str = None,
    model: str = None
) -> NLPParsedOutput:
    now = datetime.now().replace(second=0, microsecond=0)

    system_prompt = (
        f"You are a calendar scheduling parser. Current reference time is {now.isoformat()} ({now.strftime('%A')}). "
        "Convert the user's natural language command into a JSON object with EXACTLY these keys:\n"
        "- intent_type: 'schedule' or 'task'\n"
        "- title: a concise string (e.g., 'Database Study')\n"
        "- event_type: 'class', 'exam', 'event', or 'study'\n"
        "- priority: 'low', 'medium', or 'high'\n"
        "- start_time: ISO 8601 string (YYYY-MM-DDTHH:MM:SS)\n"
        "- end_time: ISO 8601 string (YYYY-MM-DDTHH:MM:SS)\n"
        "- estimated_hours: float (e.g., 2.0)\n"
        "Calculate exact dates relative to the reference time. "
        "CRITICAL: Return ONLY raw JSON. Do NOT wrap it in markdown or add conversational text."
    )

    schema = NLPParsedOutput.model_json_schema()

    try:
        use_cloud = bool(api_key) or settings.LLM_PROVIDER != "ollama"
        active_key = api_key or settings.CLOUD_API_KEY
        active_base = validate_base_url(base_url or settings.CLOUD_BASE_URL)
        active_model = model or settings.CLOUD_MODEL

        if not use_cloud:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
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
                return NLPParsedOutput.model_validate_json(clean_json_text(raw_json))
        else:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                response = await client.post(
                    f"{active_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {active_key}",
                        "HTTP-Referer": "http://localhost:5173",
                        "X-Title": "Thesis App"
                    },
                    json={
                        "model": active_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.1
                    }
                )
                response.raise_for_status()
                raw_json = response.json()["choices"][0]["message"]["content"]
                return NLPParsedOutput.model_validate_json(clean_json_text(raw_json))

    except Exception as e:
        print(f"!!! NLP LLM API Error: {e}")

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