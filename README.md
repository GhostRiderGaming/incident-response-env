---
title: Meta OpenEnv Incident Response
emoji: 🚨
colorFrom: red
colorTo: gray
sdk: docker
app_port: 8000
---
# 🚨 IncidentResponseEnv — Production Incident Response RL Environment

An [OpenEnv](https://github.com/meta-pytorch/OpenEnv)-compliant reinforcement learning environment where AI agents act as **on-call Site Reliability Engineers (SREs)**, diagnosing and remediating production outages in a simulated microservices infrastructure.

## Why Incident Response?

Every tech company runs on-call rotations. Engineers are paged at 3 AM to diagnose cascading failures across dozens of microservices. This environment trains AI agents to:

- **Triage alerts** by severity (P0-P3)
- **Diagnose root causes** by tracing dependency chains
- **Execute remediations** safely, in the correct order
- **Avoid making things worse** (wrong remediations are heavily penalized)

This fills a genuine gap in the RL/agent community — there is no existing standardized environment for training incident response agents.

## Simulated Infrastructure

```
┌──────────────────────────────────────────────┐
│           Production System (7 services)      │
│                                               │
│  API Gateway ──→ Auth Service ──→ DB Service  │
│       │                              ↑         │
│       └──→ Order Service ──→ Payment Service  │
│                │                               │
│                ├──→ Notification Service       │
│                └──→ Cache Service (Redis)      │
└──────────────────────────────────────────────┘
```

Each service has realistic metrics (CPU, memory, error rate, latency), generates log entries, and fails in realistic ways (CPU overload, memory leak, config error, disk full, cache corruption, network partition).

## Action Space (10 Tools)

| Tool | Arguments | Purpose |
|------|-----------|---------|
| `view_alerts` | `{}` | See all active alerts |
| `check_service_health` | `{"service_name": "..."}` | Check CPU, memory, latency, error rate |
| `view_service_logs` | `{"service_name": "...", "lines": 20}` | Read recent logs |
| `check_service_metrics` | `{"service_name": "...", "metric": "cpu_percent"}` | Time-series data |
| `view_dependency_map` | `{}` | Service dependency graph |
| `classify_alert` | `{"alert_id": "...", "severity": "P0"}` | Classify alert severity |
| `identify_root_cause` | `{"service_name": "...", "failure_mode": "..."}` | Diagnose root cause |
| `execute_remediation` | `{"service_name": "...", "action": "restart_service"}` | Fix the issue |
| `check_resolution` | `{}` | Check progress |
| `submit_assessment` | `{}` | End episode, get final score |

## Observation Space

Each observation includes:
- `tool_result`: Result from the last tool call (varies by tool)
- `tool_name`: Name of the tool that was called
- `error`: Error message if the action was invalid
- `progress`: Alerts classified, root causes found, remediations done
- `available_tools`: List of all available tools
- `task_info`: Current task name, difficulty, max steps

## Tasks (3 Difficulty Levels)

### Task 1: Alert Triage (Easy)
- **Scenario**: Database CPU overload → 5 alerts
- **Objective**: Classify each alert by severity (P0-P3)
- **Max steps**: 20
- **Grading**: Classification accuracy

### Task 2: Root Cause Analysis (Medium)
- **Scenario**: Cascading failure from disk exhaustion → 8 alerts, 6 services affected
- **Objective**: Classify alerts AND identify root cause service + failure mode
- **Max steps**: 30
- **Grading**: 30% classification + 40% root cause + 30% affected services

### Task 3: Full Incident Response (Hard)
- **Scenario**: Dual root cause (cache memory leak + payment config error) → 12 alerts
- **Objective**: Classify, diagnose BOTH root causes, execute remediations in correct order
- **Max steps**: 45
- **Grading**: 25% classification + 25% root cause + 25% remediation + 25% order

## Reward Function

Rewards are **incremental** (not sparse), providing feedback on every action:

| Action | Reward |
|--------|--------|
| Correct alert classification | +1.0 |
| Wrong alert classification | -0.3 |
| Correct root cause | +3.0 |
| Wrong root cause | -1.0 |
| Correct remediation | +2.0 |
| Correct remediation order | +1.0 bonus |
| Wrong remediation | -1.5 |
| Invalid action | -0.5 |
| Each step cost | -0.01 |
| Terminal bonus | +5.0 × final_score |

## Setup Instructions

### Prerequisites
- Python 3.10-3.12
- Docker (for containerized deployment)
- `openenv-core` package

### Local Development
```bash
# Clone and cd
cd incident_response_env

# Install dependencies
pip install -e .

# Run server
uvicorn server.app:app --host 0.0.0.0 --port 8000

# Open web interface
# ENABLE_WEB_INTERFACE=true uvicorn server.app:app --host 0.0.0.0 --port 8000
# Visit http://localhost:8000/web
```

### Docker
```bash
docker build -t incident-response-env .
docker run -p 8000:8000 incident-response-env
```

### Validate
```bash
openenv validate .
openenv validate --url http://localhost:8000
```

### Run Inference
```bash
export HF_TOKEN=your_token
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct

python inference.py
```

## Baseline Performance

| Task | Difficulty | Baseline Score | Steps |
|------|-----------|---------------|-------|
| Alert Triage | Easy | ~0.60-0.80 | 12-18 |
| Root Cause Analysis | Medium | ~0.40-0.60 | 20-28 |
| Full Incident Response | Hard | ~0.20-0.40 | 30-45 |

*Baseline scores measured with Qwen2.5-72B-Instruct*

## Technical Details

- **Framework**: OpenEnv (openenv-core 0.2.3)
- **Server**: FastAPI + Uvicorn
- **Models**: Pydantic v2 for type-safe action/observation
- **Grading**: Fully deterministic, reproducible
- **License**: BSD-3-Clause
