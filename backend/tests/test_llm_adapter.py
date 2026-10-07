import pytest
import json
import httpx
from unittest.mock import AsyncMock, patch
from app.services.llm_advisor import LLMAdvisor
from app.core.config import settings

@pytest.mark.asyncio
async def test_llm_advisor_skipped_when_no_key():
    with patch.object(settings, "LLM_API_KEY", ""):
        res = await LLMAdvisor.generate_incident_advisory(
            incident={"title": "Test Incident", "service": "api-gateway", "summary": "Sample summary"},
            correlated_logs=[]
        )
        assert res.advisory_status == "skipped"
        assert res.is_advisory is True
        assert res.provider_error is not None
        assert "not configured" in res.recommended_remediation[0]

@pytest.mark.asyncio
async def test_llm_advisor_openai_compatible_mock():
    mock_response_payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "root_cause_hypothesis": "Connection pool exhaustion in db-proxy cascade",
                        "recommended_remediation": ["Scale DB pool", "Review connection timeouts"],
                        "timeline_narrative": "At 14:00 db pool exhausted, cascading to auth-service."
                    })
                }
            }
        ]
    }

    with patch.object(settings, "LLM_API_KEY", "test-key-mock"), \
         patch.object(settings, "LLM_PROVIDER", "openai-compatible"), \
         patch("httpx.AsyncClient.post") as mock_post:
        
        from unittest.mock import MagicMock
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response_payload
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        res = await LLMAdvisor.generate_incident_advisory(
            incident={"title": "Cascade Outage", "service": "db-proxy", "start_time": "14:00", "end_time": "14:05"},
            correlated_logs=[{"timestamp": "14:00", "service": "db-proxy", "level": "CRITICAL", "message": "pool exhausted", "anomaly_score": 0.9}]
        )

        assert res.advisory_status == "success"
        assert "Connection pool exhaustion" in res.root_cause_hypothesis
        assert len(res.recommended_remediation) == 2

@pytest.mark.asyncio
async def test_llm_advisor_network_timeout():
    with patch.object(settings, "LLM_API_KEY", "test-key-mock"), \
         patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Mocked timeout")):
        
        res = await LLMAdvisor.generate_incident_advisory(
            incident={"title": "Test", "service": "api-gateway", "summary": "Fallback summary"},
            correlated_logs=[]
        )
        assert res.advisory_status == "error"
        assert "timed out" in res.provider_error
