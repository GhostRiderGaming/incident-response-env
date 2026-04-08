# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Incident Response Environment Client."""

from typing import Any, Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import IncidentResponseAction, IncidentResponseObservation


class IncidentResponseEnv(
    EnvClient[IncidentResponseAction, IncidentResponseObservation, State]
):
    """
    Client for the Incident Response Environment.

    This client maintains a persistent WebSocket connection to the environment server.
    Agents interact by sending tool-based actions (view_alerts, classify_alert, etc.)
    and receiving observations with tool results and progress updates.

    Example:
        >>> with IncidentResponseEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset(options={"task": "alert_triage"})
        ...     print(result.observation.task_info)
        ...
        ...     result = client.step(IncidentResponseAction(
        ...         tool_name="view_alerts", tool_args={}
        ...     ))
        ...     print(result.observation.tool_result)

    Example with Docker:
        >>> client = IncidentResponseEnv.from_docker_image("incident-response-env:latest")
        >>> try:
        ...     result = client.reset()
        ...     result = client.step(IncidentResponseAction(
        ...         tool_name="check_service_health",
        ...         tool_args={"service_name": "db_service"}
        ...     ))
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: IncidentResponseAction) -> Dict:
        """Convert IncidentResponseAction to JSON payload for step message."""
        return {
            "tool_name": action.tool_name,
            "tool_args": action.tool_args,
        }

    def _parse_result(self, payload: Dict) -> StepResult[IncidentResponseObservation]:
        """Parse server response into StepResult[IncidentResponseObservation]."""
        obs_data = payload.get("observation", {})
        observation = IncidentResponseObservation(
            tool_result=obs_data.get("tool_result"),
            tool_name=obs_data.get("tool_name", ""),
            error=obs_data.get("error"),
            progress=obs_data.get("progress", {}),
            available_tools=obs_data.get("available_tools", []),
            task_info=obs_data.get("task_info", {}),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """Parse server response into State object."""
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
