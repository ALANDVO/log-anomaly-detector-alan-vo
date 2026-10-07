import json, httpx
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.models.schemas import LLMAdvisoryResponse

TIMEOUT_SECONDS = 15.0

class LLMAdvisor:
    """Multi-provider LLM advisory adapter. Strictly grounded in verified incident log records."""

    @classmethod
    async def generate_incident_advisory(
        cls,
        incident: Dict[str, Any],
        correlated_logs: List[Dict[str, Any]],
        operator_guidance: Optional[str] = None
    ) -> LLMAdvisoryResponse:
        provider = settings.LLM_PROVIDER.lower().strip()
        model = settings.LLM_MODEL
        api_key = settings.LLM_API_KEY.strip()
        base_url = settings.LLM_BASE_URL.rstrip("/")

        if not api_key and provider not in ("ollama",):
            return LLMAdvisoryResponse(
                provider=provider, model=model, advisory_status="skipped", is_advisory=True,
                grounded_record_count=len(correlated_logs),
                root_cause_hypothesis=incident.get("root_cause_hypothesis") or "Deterministic baseline active.",
                recommended_remediation=["LLM_API_KEY is not configured on the server."],
                timeline_narrative=incident.get("summary") or "",
                provider_error="LLM_API_KEY not configured. Opt-in advisory was skipped."
            )

        log_excerpts = [
            {"timestamp": l.get("timestamp"), "service": l.get("service"), "level": l.get("level"), "message": l.get("message"), "anomaly_score": l.get("anomaly_score")}
            for l in correlated_logs[:25]
        ]

        system_prompt = (
            "You are an SRE incident postmortem assistant. Analyze the logs and respond ONLY with JSON:\n"
            '{"root_cause_hypothesis": "string", "recommended_remediation": ["step 1"], "timeline_narrative": "string"}'
        )

        user_content = (
            f"Title: {incident.get('title')}\nService: {incident.get('service')}\n"
            f"Logs: {json.dumps(log_excerpts, indent=1)}\n"
        )
        if operator_guidance:
            user_content += f"Operator Hint: {operator_guidance}\n"

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                if provider in ("openai-compatible", "openai", "openrouter", "litellm"):
                    raw = await cls._call_openai(client, base_url, model, api_key, system_prompt, user_content)
                elif provider == "anthropic":
                    raw = await cls._call_anthropic(client, model, api_key, system_prompt, user_content)
                elif provider == "gemini":
                    raw = await cls._call_gemini(client, model, api_key, system_prompt, user_content)
                elif provider == "ollama":
                    raw = await cls._call_ollama(client, base_url, model, system_prompt, user_content)
                else:
                    return LLMAdvisoryResponse(
                        provider=provider, model=model, advisory_status="error", is_advisory=True,
                        grounded_record_count=len(correlated_logs), root_cause_hypothesis="Unsupported provider",
                        recommended_remediation=[], timeline_narrative="", provider_error=f"Unknown provider '{provider}'"
                    )

            parsed = cls._parse_json(raw)
            return LLMAdvisoryResponse(
                provider=provider, model=model, advisory_status="success", is_advisory=True,
                grounded_record_count=len(correlated_logs),
                root_cause_hypothesis=parsed.get("root_cause_hypothesis", "No hypothesis produced."),
                recommended_remediation=parsed.get("recommended_remediation", ["Review logs"]),
                timeline_narrative=parsed.get("timeline_narrative", ""),
                provider_error=None
            )
        except httpx.TimeoutException:
            return LLMAdvisoryResponse(
                provider=provider, model=model, advisory_status="error", is_advisory=True,
                grounded_record_count=len(correlated_logs),
                root_cause_hypothesis=incident.get("root_cause_hypothesis") or "",
                recommended_remediation=[], timeline_narrative="",
                provider_error=f"LLM request timed out after {TIMEOUT_SECONDS}s."
            )
        except Exception as e:
            err = str(e).replace(api_key, "[REDACTED]") if api_key else str(e)
            return LLMAdvisoryResponse(
                provider=provider, model=model, advisory_status="error", is_advisory=True,
                grounded_record_count=len(correlated_logs),
                root_cause_hypothesis=incident.get("root_cause_hypothesis") or "",
                recommended_remediation=[], timeline_narrative="",
                provider_error=f"LLM failure: {err[:200]}"
            )

    @staticmethod
    async def _call_openai(client, base_url, model, api_key, system, user):
        headers = {"Content-Type": "application/json"}
        if api_key: headers["Authorization"] = f"Bearer {api_key}"
        res = await client.post(f"{base_url}/chat/completions", headers=headers, json={
            "model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0.2
        })
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]

    @staticmethod
    async def _call_anthropic(client, model, api_key, system, user):
        res = await client.post("https://api.anthropic.com/v1/messages", headers={
            "Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"
        }, json={"model": model, "system": system, "messages": [{"role": "user", "content": user}], "max_tokens": 1024})
        res.raise_for_status()
        return res.json()["content"][0]["text"]

    @staticmethod
    async def _call_gemini(client, model, api_key, system, user):
        res = await client.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}", headers={"Content-Type": "application/json"}, json={
            "systemInstruction": {"parts": [{"text": system}]}, "contents": [{"parts": [{"text": user}]}]
        })
        res.raise_for_status()
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]

    @staticmethod
    async def _call_ollama(client, base_url, model, system, user):
        res = await client.post(f"{base_url}/api/chat", json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "stream": False})
        res.raise_for_status()
        return res.json()["message"]["content"]

    @staticmethod
    def _parse_json(raw):
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e > s:
            try: return json.loads(raw[s:e+1])
            except Exception: pass
        return {"root_cause_hypothesis": raw.strip()[:200], "recommended_remediation": ["Review logs"], "timeline_narrative": raw.strip()}
