"""Enhanced inference script for Email Triage OpenEnv.

Features:
- Robust environment/config validation
- Structured logging with progress + ETA
- LLM retries with exponential backoff
- Resilient JSON parsing/fallbacks
- Per-task and overall runtime reporting

Required env vars:
- API_BASE_URL: OpenAI-compatible API base URL
- MODEL_NAME: model identifier
- HF_TOKEN or API_KEY: API token/key for model endpoint

Optional env vars:
- ENV_BASE_URL: environment server URL (default: http://localhost:8000)
- LOG_LEVEL: logging level (default: INFO)
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import backoff
import requests
from openai import OpenAI

# -----------------------------
# Configuration
# -----------------------------
API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Performance + reliability settings
MAX_STEPS = 50  # Supports up to 50 emails in an episode
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
TEMPERATURE = 0.1
MAX_TOKENS = 120

VALID_CATEGORIES = {"spam", "urgent", "follow_up", "informational"}

SYSTEM_PROMPT = (
    "You classify one email into exactly one category: "
    "spam, urgent, follow_up, informational. "
    "Return strict JSON only with keys: category (string), confidence (0-1 float)."
)

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# -----------------------------
# Helpers
# -----------------------------
def _require_env() -> None:
    missing = [
        name
        for name, value in {
            "API_BASE_URL": API_BASE_URL,
            "MODEL_NAME": MODEL_NAME,
            "HF_TOKEN/API_KEY": API_KEY,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")


def _llm_client() -> OpenAI:
    return OpenAI(api_key=API_KEY, base_url=API_BASE_URL)


def _safe_float(value: Any, default: float = 0.5) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, parsed))


def _sanitize_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    category = str(payload.get("category", "informational")).strip().lower()
    if category not in VALID_CATEGORIES:
        category = "informational"

    confidence = _safe_float(payload.get("confidence", 0.5), default=0.5)
    return {"category": category, "confidence": confidence}


def _extract_total_emails_from_observation(observation: Dict[str, Any]) -> int:
    # total = current email (1) + remaining
    remaining = int(observation.get("inbox_remaining", 0))
    return remaining + 1


# -----------------------------
# API calls (with retries where appropriate)
# -----------------------------
@backoff.on_exception(
    backoff.expo,
    (Exception,),
    max_tries=MAX_RETRIES,
    max_time=300,
)
def call_llm_with_retry(
    client: OpenAI, messages: List[Dict[str, str]]
) -> Dict[str, Any]:
    """LLM call with exponential backoff."""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        response_format={"type": "json_object"},
        timeout=REQUEST_TIMEOUT,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            payload = {}
    except json.JSONDecodeError:
        payload = {}
    return _sanitize_action(payload)


@backoff.on_exception(
    backoff.expo,
    (requests.RequestException,),
    max_tries=MAX_RETRIES,
    max_time=120,
)
def _post_with_retry(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response = requests.post(
        url,
        params=params,
        json=json_body,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


@backoff.on_exception(
    backoff.expo,
    (requests.RequestException,),
    max_tries=MAX_RETRIES,
    max_time=120,
)
def _get_with_retry(
    url: str, *, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_action_from_llm(
    client: OpenAI, observation: Dict[str, Any], feedback: str
) -> Dict[str, Any]:
    email = observation["current_email"]
    user_prompt = (
        f"Subject: {email.get('subject', '')}\n"
        f"From: {email.get('sender', '')}\n"
        f"Has attachment: {email.get('has_attachment', False)}\n"
        f"Flagged sender: {email.get('is_flagged', False)}\n"
        f"Body: {email.get('body', '')}\n"
        f"Context feedback: {feedback}\n"
        "Return JSON only."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    action = call_llm_with_retry(client, messages)
    action["email_id"] = email.get("email_id")
    return action


def _format_eta(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    rem = int(seconds % 60)
    return f"{minutes}m {rem}s"


def run_inference_with_progress(
    task_name: str, client: OpenAI
) -> Tuple[float, Dict[str, Any]]:
    """Run one task with progress tracking and robust reporting."""
    start_time = time.time()
    session_id = f"inference_{task_name}_{int(start_time)}"

    # Reset episode
    reset_payload = _post_with_retry(
        f"{ENV_BASE_URL}/reset",
        params={"task": task_name, "session_id": session_id, "seed": 7},
    )
    observation = reset_payload["observation"]
    total_emails = _extract_total_emails_from_observation(observation)

    logger.info(
        "Starting task=%s | emails=%d | session_id=%s",
        task_name,
        total_emails,
        session_id,
    )

    step_records: List[Dict[str, Any]] = []
    done = False
    info: Dict[str, Any] = {}
    total_reward = 0.0
    feedback = "none"

    for step_idx in range(MAX_STEPS):
        if done:
            break

        elapsed = time.time() - start_time
        completed = step_idx
        divisor = max(1, completed if completed > 0 else 1)
        avg_step_time = elapsed / divisor if completed > 0 else 0.0
        remaining_steps_est = max(0, total_emails - completed)
        eta = avg_step_time * remaining_steps_est
        progress = ((completed + 1) / max(1, total_emails)) * 100

        logger.info(
            "[%s] step %d/%d | %.1f%% | elapsed=%s | eta=%s",
            task_name,
            step_idx + 1,
            total_emails,
            progress,
            _format_eta(elapsed),
            _format_eta(eta),
        )

        try:
            action = get_action_from_llm(client, observation, feedback)

            step_payload = _post_with_retry(
                f"{ENV_BASE_URL}/step",
                params={"session_id": session_id},
                json_body=action,
            )

            observation = step_payload["observation"]
            reward = step_payload["reward"]
            done = bool(step_payload["done"])
            info = step_payload.get("info", {})

            reward_value = float(reward.get("value", 0.0))
            total_reward += reward_value

            feedback = (
                f"accuracy_so_far={info.get('accuracy_so_far', 0.0):.3f}, "
                f"cumulative_reward={info.get('cumulative_reward', total_reward):.3f}"
            )

            step_records.append(
                {
                    "step": step_idx + 1,
                    "action": action,
                    "reward": reward_value,
                    "done": done,
                    "accuracy_so_far": info.get("accuracy_so_far", 0.0),
                    "emails_processed": info.get("emails_processed", step_idx + 1),
                }
            )
        except Exception as exc:
            logger.error("[%s] step %d failed: %s", task_name, step_idx + 1, exc)
            # Continue to next attempt rather than failing task immediately
            continue

    # Fetch final grade from deterministic grader endpoint
    try:
        grade_payload = _get_with_retry(
            f"{ENV_BASE_URL}/grade",
            params={"session_id": session_id},
        )
        final_score = float(grade_payload.get("score", 0.0))
    except Exception as exc:
        logger.error("[%s] grade retrieval failed: %s", task_name, exc)
        final_score = 0.0

    task_runtime = time.time() - start_time

    logger.info(
        "Completed task=%s | score=%.3f | processed=%s | total_reward=%.3f | runtime=%s",
        task_name,
        final_score,
        info.get("emails_processed", len(step_records)),
        total_reward,
        _format_eta(task_runtime),
    )

    details = {
        "task": task_name,
        "session_id": session_id,
        "score": round(final_score, 4),
        "steps_executed": len(step_records),
        "done": done,
        "total_reward": round(total_reward, 4),
        "runtime_seconds": round(task_runtime, 2),
        "final_info": info,
        "records": step_records,
    }
    return final_score, details


def main() -> Dict[str, Any]:
    """Run complete inference pipeline across easy/medium/hard."""
    _require_env()

    logger.info("=== Email Triage Inference Starting ===")
    logger.info("Model: %s", MODEL_NAME)
    logger.info("API Base: %s", API_BASE_URL)
    logger.info("Env Base: %s", ENV_BASE_URL)
    logger.info(
        "Max steps: %d | Retries: %d | Timeout: %ss",
        MAX_STEPS,
        MAX_RETRIES,
        REQUEST_TIMEOUT,
    )

    client = _llm_client()
    tasks = ["easy", "medium", "hard"]
    results: Dict[str, Dict[str, Any]] = {}

    overall_start = time.time()

    for task in tasks:
        score, details = run_inference_with_progress(task, client)
        results[task] = {"score": score, "details": details}

    total_time = time.time() - overall_start
    overall_score = sum(results[t]["score"] for t in tasks) / len(tasks)

    logger.info("=" * 60)
    logger.info("FINAL RESULTS")
    logger.info("=" * 60)
    for task in tasks:
        logger.info(
            "%-10s | Score: %.3f | Runtime: %ss",
            task.upper(),
            results[task]["score"],
            results[task]["details"]["runtime_seconds"],
        )
    logger.info("=" * 60)
    logger.info("Overall Score: %.3f", overall_score)
    logger.info("Total Runtime: %.1fs (%.1f min)", total_time, total_time / 60)
    logger.info("Status: %s", "✅ PASS" if total_time < 1200 else "❌ TIMEOUT")
    logger.info("=" * 60)

    summary = {
        "overall_score": round(overall_score, 4),
        "total_runtime_seconds": round(total_time, 2),
        "results": results,
    }

    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
