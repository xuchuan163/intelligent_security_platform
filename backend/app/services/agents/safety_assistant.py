from app.infrastructure.llm.qwen_client import qwen


class SafetyAssistantService:
    def __init__(self):
        self.client = qwen

    def chat(self, message: str, context: dict | None = None) -> dict:
        messages = []
        if context:
            messages.append({
                "role": "system",
                "content": f"当前上下文：{context}"
            })
        messages.append({"role": "user", "content": message})
        return self.client.chat(messages)

    def explain_project_risk(self, project_id: str, profile_data: dict | None) -> dict:
        if profile_data is None:
            return {
                "available": self.client.available,
                "message": "未找到项目画像数据，无法生成解释。",
                "content": None,
            }

        context = (
            f"项目 {project_id} 当前风险分为 {profile_data.get('total_risk_score')}，"
            f"风险等级为 {profile_data.get('risk_level')}。"
            f"风险标签：{profile_data.get('risk_tags')}。"
            f"已触发规则：{profile_data.get('evidence', [])}。"
        )
        return self.chat(f"请解释{project_id}项目的风险状况并给出管理建议。", {"project_context": context})

    def suggest_hazard_rectification(self, hazard_info: dict) -> dict:
        context = f"隐患详情：{hazard_info}"
        return self.chat(f"请为以下隐患提供分类、定级、整改措施和复查要点建议。{context}")


safety_assistant = SafetyAssistantService()
