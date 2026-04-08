"""
Inference Script for IncidentResponseEnv
=========================================
MANDATORY FORMAT — Must emit [START], [STEP], [END] logs exactly as specified.

Environment Variables:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.
    IMAGE_NAME     The name of the local Docker image (optional, for from_docker_image)

STDOUT FORMAT:
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import asyncio
import json
import os
import textwrap
from typing import Any, Dict, List, Optional

from openai import OpenAI

from incident_response_env import IncidentResponseAction, IncidentResponseEnv

# ──────────────── Configuration ────────────────

IMAGE_NAME = os.getenv("IMAGE_NAME")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
BENCHMARK = "incident_response_env"
MAX_STEPS_PER_TASK = {"alert_triage": 20, "root_cause_analysis": 30, "full_incident_response": 45}
TEMPERATURE = 0.3
MAX_TOKENS = 500

SYSTEM_PROMPT = textwrap.dedent("""
You are an expert Site Reliability Engineer (SRE) responding to a production incident.
You interact with the environment using tool calls. Each turn, respond with a JSON object:
{"tool_name": "<tool>", "tool_args": {<args>}}

Available tools:
- view_alerts: {} — List all active alerts
- check_service_health: {"service_name": "<name>"} — Check service metrics
- view_service_logs: {"service_name": "<name>", "lines": 20} — Read service logs
- check_service_metrics: {"service_name": "<name>", "metric": "<cpu_percent|memory_percent|error_rate_percent|latency_ms>"} — Time-series data
- view_dependency_map: {} — See service dependencies
- classify_alert: {"alert_id": "<id>", "severity": "<P0|P1|P2|P3>"} — Classify alert severity
- identify_root_cause: {"service_name": "<name>", "failure_mode": "<cpu_overload|memory_leak|config_error|disk_full|cache_corruption|network_partition>"} — Identify root cause
- execute_remediation: {"service_name": "<name>", "action": "<restart_service|scale_up|rollback_config|clear_cache|failover_db>"} — Fix the issue
- check_resolution: {} — Check progress
- submit_assessment: {} — Finalize and get score

Strategy:
1. First, view_alerts to see the incident
2. Check health/logs/metrics of affected services
3. View dependency map to trace cascading failures
4. Classify each alert by severity
5. Identify root cause(s)
6. If required, execute remediations in proper order
7. Submit assessment when done

Reply with ONLY a JSON object. No markdown, no explanation.
""").strip()


# ──────────────── Logging ────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}", flush=True)


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)


# ──────────────── LLM Interaction ────────────────

def parse_llm_response(text: str) -> Dict[str, Any]:
    """Parse LLM response into tool_name and tool_args."""
    text = text.strip()
    # Try to extract JSON from the response
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
        tool_name = data.get("tool_name", "view_alerts")
        tool_args = data.get("tool_args", {})
        return {"tool_name": tool_name, "tool_args": tool_args}
    except (json.JSONDecodeError, KeyError):
        # Fallback: try to find tool_name in the text
        return {"tool_name": "view_alerts", "tool_args": {}}


def get_llm_action(client: OpenAI, messages: List[Dict]) -> Dict[str, Any]:
    """Ask the LLM to decide the next action."""
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        return parse_llm_response(text)
    except Exception as exc:
        print(f"[DEBUG] LLM request failed: {exc}", flush=True)
        return {"tool_name": "view_alerts", "tool_args": {}}


# ──────────────── Main Loop ────────────────

async def run_task(task_name: str, env_url: str) -> Dict:
    """Run a single task and return the result."""
    oai_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    if IMAGE_NAME:
        env = await IncidentResponseEnv.from_docker_image(IMAGE_NAME)
    else:
        env = IncidentResponseEnv(base_url=env_url)

    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False
    max_steps = MAX_STEPS_PER_TASK.get(task_name, 30)

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    try:
        # Connect and reset
        if not IMAGE_NAME:
            await env.connect()
        result = await env.reset(options={"task": task_name})

        obs = result.observation
        messages.append({
            "role": "user",
            "content": f"Task: {task_name}\nObjective: {obs.task_info.get('objective', '')}\nInitial state: {json.dumps(obs.tool_result, default=str)}\n\nDecide your first action."
        })

        for step in range(1, max_steps + 1):
            if result.done:
                break

            # Get LLM action
            action_data = get_llm_action(oai_client, messages)
            tool_name = action_data["tool_name"]
            tool_args = action_data["tool_args"]

            # Execute action
            action = IncidentResponseAction(tool_name=tool_name, tool_args=tool_args)
            result = await env.step(action)
            obs = result.observation

            reward = result.reward or 0.0
            done = result.done
            error = obs.error

            rewards.append(reward)
            steps_taken = step

            action_str = f"{tool_name}({json.dumps(tool_args, default=str)})"
            log_step(step=step, action=action_str, reward=reward, done=done, error=error)

            # Add to conversation
            messages.append({
                "role": "assistant",
                "content": json.dumps(action_data, default=str)
            })

            result_summary = json.dumps({
                "tool_result": obs.tool_result,
                "reward": reward,
                "progress": obs.progress,
                "error": error,
            }, default=str)

            messages.append({
                "role": "user",
                "content": f"Result: {result_summary}\n\nDecide your next action."
            })

            # Keep conversation from getting too long
            if len(messages) > 20:
                messages = messages[:1] + messages[-18:]

            if done:
                break

        # Extract final score from last observation
        if obs.tool_result and isinstance(obs.tool_result, dict):
            final_score = obs.tool_result.get("final_score", {})
            if isinstance(final_score, dict):
                score = final_score.get("final_score", 0.0)
            else:
                score = float(final_score) if final_score else 0.0
        else:
            score = 0.0

        score = min(max(score, 0.0), 1.0)
        success = score >= 0.1

    except Exception as exc:
        print(f"[DEBUG] Task {task_name} error: {exc}", flush=True)
        score = 0.0
        success = False

    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error: {e}", flush=True)
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return {"task": task_name, "score": score, "steps": steps_taken, "success": success}


async def main():
    """Run all three tasks sequentially."""
    env_url = os.getenv("ENV_URL", "http://localhost:8000")
    tasks = ["alert_triage", "root_cause_analysis", "full_incident_response"]
    results = []

    for task_name in tasks:
        result = await run_task(task_name, env_url)
        results.append(result)

    # Print summary
    print("\n=== FINAL RESULTS ===", flush=True)
    for r in results:
        print(f"  {r['task']}: score={r['score']:.2f} steps={r['steps']} success={r['success']}", flush=True)
    avg_score = sum(r["score"] for r in results) / len(results) if results else 0.0
    print(f"  Average score: {avg_score:.2f}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
