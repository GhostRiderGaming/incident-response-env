"""
Task Definitions for IncidentResponseEnv.

Three tasks with increasing difficulty, each with clear objectives and constraints.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TaskConfig:
    """Configuration for a single task."""
    name: str
    difficulty: str
    description: str
    incident_id: int
    max_steps: int
    required_actions: List[str]
    grading_weights: Dict[str, float]
    objective: str


TASKS = {
    "alert_triage": TaskConfig(
        name="alert_triage",
        difficulty="easy",
        description="Classify 5 alerts by severity (P0-P3). A single database service is experiencing high CPU load, causing cascading effects on dependent services.",
        incident_id=1,
        max_steps=20,
        required_actions=["classify_alert"],
        grading_weights={"classification": 1.0},
        objective="Correctly classify all 5 alerts by severity level (P0=Critical, P1=High, P2=Medium, P3=Low). Use view_alerts and check_service_health to gather information before classifying.",
    ),
    "root_cause_analysis": TaskConfig(
        name="root_cause_analysis",
        difficulty="medium",
        description="Diagnose a cascading failure across 6 services. Database disk exhaustion is causing failures in all dependent services. Classify 8 alerts AND identify the root cause service and failure mode.",
        incident_id=2,
        max_steps=30,
        required_actions=["classify_alert", "identify_root_cause"],
        grading_weights={"classification": 0.3, "root_cause": 0.4, "affected_services": 0.3},
        objective="Classify all 8 alerts by severity, then identify the root cause service and failure reason. Use view_service_logs, check_service_metrics, and view_dependency_map to trace the failure chain.",
    ),
    "full_incident_response": TaskConfig(
        name="full_incident_response",
        difficulty="hard",
        description="Respond to a complex dual-root-cause incident. Cache memory leak AND payment config error causing overlapping failures. Classify 12 alerts, identify BOTH root causes, and execute remediations in dependency-safe order.",
        incident_id=3,
        max_steps=45,
        required_actions=["classify_alert", "identify_root_cause", "execute_remediation"],
        grading_weights={"classification": 0.25, "root_cause": 0.25, "remediation": 0.25, "order": 0.25},
        objective="Full incident response: classify all alerts, identify both root causes (cache_service memory_leak and payment_service config_error), execute correct remediations (restart_service for cache, rollback_config for payment), in dependency-safe order (cache first, then payment).",
    ),
}

TASK_LIST = list(TASKS.keys())
