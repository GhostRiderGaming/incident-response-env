# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Incident Response Environment — Production Incident Response RL Environment.

An OpenEnv-compliant environment where AI agents act as on-call SREs,
diagnosing and remediating production outages in a simulated microservices infrastructure.

Tools available:
    - view_alerts: See all active monitoring alerts
    - check_service_health: Check CPU, memory, latency, error rate of a service
    - view_service_logs: Read recent log entries from a service
    - check_service_metrics: Get time-series metrics for a service
    - view_dependency_map: See the microservice dependency graph
    - classify_alert: Classify an alert by severity (P0-P3)
    - identify_root_cause: Identify the root cause service and failure mode
    - execute_remediation: Execute a remediation action on a service
    - check_resolution: Check current incident resolution progress
    - submit_assessment: Submit final assessment and end the episode

Example:
    >>> from incident_response_env import IncidentResponseEnv, IncidentResponseAction
    >>>
    >>> with IncidentResponseEnv(base_url="http://localhost:8000") as client:
    ...     result = client.reset(options={"task": "alert_triage"})
    ...     result = client.step(IncidentResponseAction(
    ...         tool_name="view_alerts", tool_args={}
    ...     ))
    ...     print(result.observation.tool_result)
"""

from .client import IncidentResponseEnv
from .models import IncidentResponseAction, IncidentResponseObservation

__all__ = [
    "IncidentResponseAction",
    "IncidentResponseObservation",
    "IncidentResponseEnv",
]
