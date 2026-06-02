from app.services.agents.safety_assistant import SafetyAssistantService


def test_assistant_returns_clear_error_when_key_missing():
    service = SafetyAssistantService()
    service.client.api_key = None
    service.client.available = False

    result = service.chat("解释A项目风险", context={})

    assert result["available"] is False
    assert "DASHSCOPE_API_KEY" in result["message"]
