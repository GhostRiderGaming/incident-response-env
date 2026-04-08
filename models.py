# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Incident Response Environment.

Defines typed Action and Observation models for type-safe
communication between client and server.
"""

from typing import Any, Dict, List, Optional

from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class IncidentResponseAction(Action):
    """Action for the Incident Response environment.

    The agent sends a tool call via this action. The tool_name determines
    which environment tool to invoke, and tool_args provides the arguments.
    """

    tool_name: str = Field(
        ...,
        description="Name of the tool to invoke. Available tools: "
        "view_alerts, check_service_health, view_service_logs, "
        "check_service_metrics, view_dependency_map, classify_alert, "
        "identify_root_cause, execute_remediation, check_resolution, "
        "submit_assessment",
    )
    tool_args: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments for the tool call. Varies by tool.",
    )


class IncidentResponseObservation(Observation):
    """Observation from the Incident Response environment.

    Contains the result of the last tool call, current progress,
    and environment state information.
    """

    tool_result: Any = Field(default=None, description="Result from the last tool call")
    tool_name: str = Field(default="", description="Name of the last tool called")
    error: Optional[str] = Field(default=None, description="Error message if the action failed")
    progress: Dict[str, Any] = Field(
        default_factory=dict,
        description="Current progress: alerts classified, root causes found, etc.",
    )
    available_tools: List[str] = Field(
        default_factory=lambda: [
            "view_alerts", "check_service_health", "view_service_logs",
            "check_service_metrics", "view_dependency_map", "classify_alert",
            "identify_root_cause", "execute_remediation", "check_resolution",
            "submit_assessment",
        ],
        description="List of available tool names",
    )
    task_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Information about the current task",
    )
