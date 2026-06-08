from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class WecomDeliveryResult:
    response_status_code: int | None
    response_body: str | None
    delivery_status: str
    error_message: str | None
    elapsed_ms: int | None


def build_wecom_text_payload(content: str) -> dict[str, Any]:
    return {
        "msgtype": "text",
        "text": {
            "content": content,
        },
    }


def build_wecom_markdown_payload(content: str) -> dict[str, Any]:
    return {
        "msgtype": "markdown",
        "markdown": {
            "content": content,
        },
    }


def _evaluate_wecom_response(status_code: int | None, response_body: str | None) -> tuple[str, str | None]:
    if status_code is None:
        return "failed", "No HTTP response"
    if status_code < 200 or status_code >= 300:
        return "failed", f"HTTP {status_code}"

    if not response_body:
        return "failed", "Empty response body"

    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError:
        return "failed", "Invalid JSON response"

    errcode = payload.get("errcode")
    if errcode == 0:
        return "success", None
    return "failed", str(payload.get("errmsg") or f"errcode={errcode}")


def send_wecom_bot_message(
    target_url: str,
    *,
    message_body: dict[str, Any],
    timeout_seconds: int | None = None,
    http_client: httpx.Client | None = None,
) -> WecomDeliveryResult:
    timeout = timeout_seconds or settings.webhook_timeout_seconds
    started = time.perf_counter()

    try:
        if http_client is not None:
            response = http_client.post(target_url, json=message_body, timeout=timeout)
        else:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(target_url, json=message_body)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        body_text = response.text
        delivery_status, error_message = _evaluate_wecom_response(response.status_code, body_text)
        return WecomDeliveryResult(
            response_status_code=response.status_code,
            response_body=body_text,
            delivery_status=delivery_status,
            error_message=error_message,
            elapsed_ms=elapsed_ms,
        )
    except httpx.TimeoutException as exc:
        return WecomDeliveryResult(
            response_status_code=None,
            response_body=None,
            delivery_status="failed",
            error_message=f"timeout: {exc}",
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )
    except httpx.HTTPError as exc:
        return WecomDeliveryResult(
            response_status_code=None,
            response_body=None,
            delivery_status="failed",
            error_message=str(exc),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )
