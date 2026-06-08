# Prompts

本目录用于 P2 阶段管理 Agent Prompt 模板。

当前状态：

- MVP 仅有 SafetyAssistant；
- Prompt 逻辑位于 `backend/app/services/agents/safety_assistant.py` 和 LLM client 相关代码中；
- 尚未引入 Prompt 版本表和多 Agent 编排。

Prompt 编写边界：

- 关键结论必须引用结构化 evidence；
- 涉及停工、清退、处罚等建议必须要求人工复核；
- 不得向 LLM 传入身份证号、体检明细、人脸原图或原始视频。

