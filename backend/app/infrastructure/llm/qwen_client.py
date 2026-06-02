import httpx
from app.core.config import settings

SYSTEM_PROMPT = """你是中建集团项目工地安全智能平台的安全助手。
你只能基于已提供的结构化事实、规则命中和证据摘要进行解释。
强规则和数据库事实优先于自然语言推理。
涉及停工、限制作业、处罚、清退等动作时，只能输出建议，必须提示人工复核。
不要输出身份证、手机号、健康明细、人脸原始图像等敏感信息。"""


class QwenClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, base_url: str | None = None):
        self.api_key = api_key or settings.dashscope_api_key
        self.model = model or settings.qwen_model
        self.base_url = base_url or settings.qwen_base_url
        self.available = bool(self.api_key)

    def chat(self, messages: list[dict], temperature: float = 0.3) -> dict:
        if not self.available:
            return {
                "available": False,
                "message": "Qwen 助手未配置。请在 .env 中设置 DASHSCOPE_API_KEY。",
                "content": None,
            }

        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": full_messages,
                        "temperature": temperature,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "available": True,
                        "message": "ok",
                        "content": data["choices"][0]["message"]["content"],
                    }
                return {
                    "available": True,
                    "message": f"API error: {response.status_code}",
                    "content": None,
                }
        except Exception as e:
            return {
                "available": True,
                "message": f"Request failed: {str(e)}",
                "content": None,
            }


qwen = QwenClient()
