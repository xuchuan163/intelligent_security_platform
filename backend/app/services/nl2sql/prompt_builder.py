from typing import Any

from app.services.nl2sql.schema_context import SchemaContext, render_schema_context


def build_candidate_sql_prompt(
    question: str,
    schema_context: SchemaContext,
    clarification_context: dict[str, Any] | None = None,
) -> str:
    sections = [
        "You generate candidate SQL for a construction safety platform.",
        "",
        "Rules:",
        "- Return exactly one MySQL SELECT statement.",
        "- Do not return Markdown, prose, comments, code fences, or explanations.",
        "- Do not use SELECT *.",
        "- Use only the tables and fields listed below.",
        "- Do not include company_id, tenant_id, or org_path predicates; the audit layer injects them.",
        "- Do not add data-scope project_id predicates; the audit layer injects authorized project scope.",
        "- Do not query audit, memory, authentication, or internal Agent tables.",
        "- If the question is ambiguous, return CLARIFICATION_REQUIRED: <short reason>.",
        "",
        render_schema_context(schema_context),
    ]
    if clarification_context:
        sections.extend(
            [
                "",
                "Clarification context:",
                f"- Original question: {clarification_context.get('original_question', '')}",
                f"- Clarification needed: {clarification_context.get('clarification_prompt', '')}",
            ]
        )
        for index, reply in enumerate(clarification_context.get("replies") or [], start=1):
            sections.append(f"- User clarification {index}: {reply}")
        sections.extend(
            [
                "- Use the clarified intent above. Do not ask for clarification again unless critical details are still missing.",
                "",
                f"Refined question: {clarification_context.get('refined_question', question)}",
            ]
        )
    else:
        sections.extend(["", f"Question: {question}"])
    sections.extend(["", "Candidate SQL:"])
    return "\n".join(sections)
