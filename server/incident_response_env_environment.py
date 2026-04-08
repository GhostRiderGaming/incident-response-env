# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Incident Response Environment Implementation.

Production incident response environment where an AI agent acts as an on-call SRE,
diagnosing and remediating outages in a simulated microservices infrastructure.
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import IncidentResponseAction, IncidentResponseObservation
    from ..infrastructure import InfrastructureState, SERVICE_DEFINITIONS, FAILURE_MODES
    from ..incidents import INCIDENTS, INCIDENT_BY_NAME
    from ..tasks import TASKS, TASK_LIST
    from ..grader import Grader
except ImportError:
    from models import IncidentResponseAction, IncidentResponseObservation
    from infrastructure import InfrastructureState, SERVICE_DEFINITIONS, FAILURE_MODES
    from incidents import INCIDENTS, INCIDENT_BY_NAME
    from tasks import TASKS, TASK_LIST
    from grader import Grader


VALID_SEVERITIES = {"P0", "P1", "P2", "P3"}
VALID_REMEDIATIONS = {"restart_service", "scale_up", "rollback_config", "clear_cache", "failover_db"}


class IncidentResponseEnvironment(Environment):
    """
    Production Incident Response RL Environment.

    The agent acts as an on-call SRE responding to production incidents.
    Available tools: view_alerts, check_service_health, view_service_logs,
    check_service_metrics, view_dependency_map, classify_alert,
    identify_root_cause, execute_remediation, check_resolution, submit_assessment.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        """Initialize the incident response environment."""
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._infra = InfrastructureState()
        self._grader: Optional[Grader] = None
        self._task_name: str = "alert_triage"
        self._incident = None
        self._task_config = None
        self._done = False
        self._total_reward = 0.0
        self._rewards: List[float] = []
        self._last_action_error: Optional[str] = None

        # Tool dispatch table
        self._tools = {
            "view_alerts": self._tool_view_alerts,
            "check_service_health": self._tool_check_service_health,
            "view_service_logs": self._tool_view_service_logs,
            "check_service_metrics": self._tool_check_service_metrics,
            "view_dependency_map": self._tool_view_dependency_map,
            "classify_alert": self._tool_classify_alert,
            "identify_root_cause": self._tool_identify_root_cause,
            "execute_remediation": self._tool_execute_remediation,
            "check_resolution": self._tool_check_resolution,
            "submit_assessment": self._tool_submit_assessment,
        }

    def reset(self, seed: int = None, options: Dict[str, Any] = None) -> IncidentResponseObservation:
        """Reset the environment for a new episode.

        Args:
            seed: Optional random seed for reproducibility
            options: Optional dict with 'task' key to select task name

        Returns:
            Initial observation with task info and available tools
        """
        options = options or {}
        self._task_name = options.get("task", "alert_triage")

        if self._task_name not in TASKS:
            self._task_name = "alert_triage"

        self._task_config = TASKS[self._task_name]
        self._incident = INCIDENTS[self._task_config.incident_id]

        # Reset state
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._done = False
        self._total_reward = 0.0
        self._rewards = []
        self._last_action_error = None

        # Reset infrastructure and inject failures
        actual_seed = seed if seed is not None else 42
        self._infra.reset_to_healthy(actual_seed)
        for injection in self._incident.failure_injections:
            self._infra.inject_failure(
                injection["service"],
                injection["failure_mode"],
                is_root_cause=True,
            )

        # Reset grader
        self._grader = Grader(self._task_config, self._incident)

        return IncidentResponseObservation(
            done=False,
            reward=0.0,
            tool_result={
                "message": f"Incident Response Environment ready. Task: {self._task_name}",
                "incident_summary": self._incident.description,
                "num_alerts": len(self._incident.alerts),
                "services": list(SERVICE_DEFINITIONS.keys()),
            },
            tool_name="reset",
            progress=self._get_progress(),
            task_info={
                "name": self._task_config.name,
                "difficulty": self._task_config.difficulty,
                "description": self._task_config.description,
                "objective": self._task_config.objective,
                "max_steps": self._task_config.max_steps,
                "required_actions": self._task_config.required_actions,
            },
        )

    def step(self, action: IncidentResponseAction) -> IncidentResponseObservation:
        """Execute a step in the environment.

        Args:
            action: IncidentResponseAction with tool_name and tool_args

        Returns:
            IncidentResponseObservation with tool result and updated progress
        """
        if self._done:
            return IncidentResponseObservation(
                done=True,
                reward=0.0,
                tool_result={"error": "Episode is already done. Call reset() to start a new episode."},
                tool_name=action.tool_name,
                error="Episode already terminated",
                progress=self._get_progress(),
                task_info=self._get_task_info(),
            )

        self._state.step_count += 1
        self._grader.record_step()
        self._last_action_error = None

        # Check step limit
        if self._state.step_count > self._task_config.max_steps:
            self._done = True
            score_result = self._grader.compute_final_score()
            reward = -0.5
            self._rewards.append(reward)
            self._total_reward += reward
            return IncidentResponseObservation(
                done=True,
                reward=reward,
                tool_result={
                    "message": "Episode terminated: maximum steps exceeded",
                    "final_score": score_result,
                },
                tool_name="timeout",
                progress=self._get_progress(),
                task_info=self._get_task_info(),
            )

        # Dispatch tool
        tool_fn = self._tools.get(action.tool_name)
        if tool_fn is None:
            self._last_action_error = f"Unknown tool: {action.tool_name}"
            reward = -0.5
            self._rewards.append(reward)
            self._total_reward += reward
            self._grader.invalid_actions += 1
            return IncidentResponseObservation(
                done=False,
                reward=reward,
                tool_result=None,
                tool_name=action.tool_name,
                error=self._last_action_error,
                progress=self._get_progress(),
                task_info=self._get_task_info(),
            )

        result, reward = tool_fn(action.tool_args)
        self._rewards.append(reward)
        self._total_reward += reward

        # Check safety termination (3+ wrong remediations)
        if self._grader.wrong_remediations >= 3:
            self._done = True
            score_result = self._grader.compute_final_score()
            return IncidentResponseObservation(
                done=True,
                reward=reward,
                tool_result={
                    "message": "Episode terminated: too many wrong remediations (you made the outage worse!)",
                    "final_score": score_result,
                },
                tool_name=action.tool_name,
                progress=self._get_progress(),
                task_info=self._get_task_info(),
            )

        return IncidentResponseObservation(
            done=self._done,
            reward=reward,
            tool_result=result,
            tool_name=action.tool_name,
            error=self._last_action_error,
            progress=self._get_progress(),
            task_info=self._get_task_info(),
        )

    @property
    def state(self) -> State:
        """Get the current environment state."""
        return self._state

    # ──────────────────── Tool Implementations ────────────────────

    def _tool_view_alerts(self, args: Dict) -> tuple:
        """View all active alerts for the current incident."""
        alerts = [
            {
                "id": a.id,
                "service": a.service,
                "title": a.title,
                "description": a.description,
                "timestamp": a.timestamp,
            }
            for a in self._incident.alerts
        ]
        return {"alerts": alerts, "count": len(alerts)}, -0.01  # small step cost

    def _tool_check_service_health(self, args: Dict) -> tuple:
        """Check the health of a specific service."""
        service_name = args.get("service_name", "")
        info = self._infra.get_service_info(service_name)
        if info is None:
            self._last_action_error = f"Service '{service_name}' not found. Available: {list(SERVICE_DEFINITIONS.keys())}"
            return {"error": self._last_action_error}, -0.1
        return info, -0.01

    def _tool_view_service_logs(self, args: Dict) -> tuple:
        """View recent logs for a service."""
        service_name = args.get("service_name", "")
        num_lines = min(args.get("lines", 20), 30)
        if service_name not in SERVICE_DEFINITIONS:
            self._last_action_error = f"Service '{service_name}' not found"
            return {"error": self._last_action_error}, -0.1
        logs = self._infra.generate_logs(service_name, num_lines)
        return {"service": service_name, "logs": logs}, -0.01

    def _tool_check_service_metrics(self, args: Dict) -> tuple:
        """Check time-series metrics for a service."""
        service_name = args.get("service_name", "")
        metric = args.get("metric", "cpu_percent")
        if service_name not in SERVICE_DEFINITIONS:
            self._last_action_error = f"Service '{service_name}' not found"
            return {"error": self._last_action_error}, -0.1
        valid_metrics = ["cpu_percent", "memory_percent", "error_rate_percent", "latency_ms", "requests_per_sec"]
        if metric not in valid_metrics:
            self._last_action_error = f"Invalid metric '{metric}'. Valid: {valid_metrics}"
            return {"error": self._last_action_error}, -0.1
        data = self._infra.get_metrics_timeseries(service_name, metric)
        return {"service": service_name, "metric": metric, "timeseries": data}, -0.01

    def _tool_view_dependency_map(self, args: Dict) -> tuple:
        """View the service dependency graph."""
        dep_map = self._infra.get_dependency_map()
        return {"dependency_map": dep_map, "description": "service -> [dependencies]"}, -0.01

    def _tool_classify_alert(self, args: Dict) -> tuple:
        """Classify an alert by severity."""
        alert_id = args.get("alert_id", "")
        severity = args.get("severity", "").upper()

        if severity not in VALID_SEVERITIES:
            self._last_action_error = f"Invalid severity '{severity}'. Valid: P0, P1, P2, P3"
            return {"error": self._last_action_error}, -0.3

        reward, feedback = self._grader.record_classification(alert_id, severity)
        return {"alert_id": alert_id, "severity": severity, "feedback": feedback}, reward

    def _tool_identify_root_cause(self, args: Dict) -> tuple:
        """Identify the root cause of the incident."""
        service = args.get("service_name", "")
        failure_mode = args.get("failure_mode", "")

        if service not in SERVICE_DEFINITIONS:
            self._last_action_error = f"Service '{service}' not found"
            return {"error": self._last_action_error}, -0.5

        valid_modes = list(FAILURE_MODES.keys())
        if failure_mode not in valid_modes:
            self._last_action_error = f"Invalid failure_mode '{failure_mode}'. Valid: {valid_modes}"
            return {"error": self._last_action_error}, -0.3

        reward, feedback = self._grader.record_root_cause(service, failure_mode)
        return {"service": service, "failure_mode": failure_mode, "feedback": feedback}, reward

    def _tool_execute_remediation(self, args: Dict) -> tuple:
        """Execute a remediation action on a service."""
        service = args.get("service_name", "")
        action = args.get("action", "")

        if service not in SERVICE_DEFINITIONS:
            self._last_action_error = f"Service '{service}' not found"
            return {"error": self._last_action_error}, -0.5

        if action not in VALID_REMEDIATIONS:
            self._last_action_error = f"Invalid action '{action}'. Valid: {list(VALID_REMEDIATIONS)}"
            return {"error": self._last_action_error}, -0.3

        reward, feedback = self._grader.record_remediation(service, action)
        return {"service": service, "action": action, "feedback": feedback}, reward

    def _tool_check_resolution(self, args: Dict) -> tuple:
        """Check the current incident resolution status."""
        score_result = self._grader.compute_final_score()
        return {
            "current_score": score_result["final_score"],
            "component_scores": score_result["component_scores"],
            "alerts_classified": len(self._grader.classifications),
            "total_alerts": len(self._incident.alerts),
            "root_causes_identified": len(self._grader.root_causes),
            "expected_root_causes": len(self._incident.root_causes),
            "remediations_executed": len(self._grader.remediations),
            "expected_remediations": len(self._incident.expected_remediations),
        }, -0.01

    def _tool_submit_assessment(self, args: Dict) -> tuple:
        """Submit final assessment and end the episode."""
        self._done = True
        score_result = self._grader.compute_final_score()
        # Terminal bonus based on overall score
        bonus = score_result["final_score"] * 5.0
        return {
            "message": "Assessment submitted. Episode complete.",
            "final_score": score_result,
        }, bonus

    # ──────────────────── Helpers ────────────────────

    def _get_progress(self) -> Dict:
        """Get current progress summary."""
        if self._grader is None:
            return {}
        return {
            "alerts_classified": len(self._grader.classifications),
            "total_alerts": len(self._incident.alerts) if self._incident else 0,
            "root_causes_found": len(self._grader.root_causes),
            "remediations_done": len(self._grader.remediations),
            "steps_taken": self._state.step_count,
            "max_steps": self._task_config.max_steps if self._task_config else 0,
            "total_reward": round(self._total_reward, 2),
        }

    def _get_task_info(self) -> Dict:
        """Get task information."""
        if self._task_config is None:
            return {}
        return {
            "name": self._task_config.name,
            "difficulty": self._task_config.difficulty,
            "max_steps": self._task_config.max_steps,
        }
