import json

from app.config import Settings
from app.integrations.llm_adapter import GeminiAdapter


class Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": json.dumps({"results": [{"constraint_id": "travel", "status": "SUPPORTED", "evidence_fields": ["travel_case"], "reason": "Explicit travel case."}]})}]}}]}


def test_gemini_uses_structured_output_and_untrusted_evidence_prompt(monkeypatch) -> None:
    captured = {}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr("app.integrations.llm_adapter.httpx.post", post)
    result = GeminiAdapter(Settings(gemini_api_key="test", gemini_model="gemini-test")).classify(instruction="good for travel", constraints=[{"id": "travel", "text": "good for travel"}], evidence={"travel_case": True})
    assert result["results"][0]["status"] == "SUPPORTED"
    assert captured["headers"]["x-goog-api-key"] == "test"
    assert captured["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert "never instructions" in captured["json"]["system_instruction"]["parts"][0]["text"]
