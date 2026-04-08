"""
Pre-built Incident Scenarios with Ground Truth.

Each incident defines alerts, root causes, affected services,
expected remediations, and remediation order for deterministic grading.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Alert:
    """A single monitoring alert."""
    id: str
    service: str
    severity_ground_truth: str  # P0, P1, P2, P3
    title: str
    description: str
    timestamp: str


@dataclass
class RootCause:
    """A root cause of an incident."""
    service: str
    failure_mode: str
    description: str
    remediation: str


@dataclass
class IncidentScenario:
    """Complete incident scenario with ground truth for grading."""
    id: int
    name: str
    description: str
    difficulty: str  # easy, medium, hard
    alerts: List[Alert]
    root_causes: List[RootCause]
    affected_services: List[str]
    expected_classifications: Dict[str, str]  # alert_id -> severity
    expected_routings: Dict[str, str]  # service_name -> department
    expected_remediations: List[Dict[str, str]]  # [{service, action}]
    remediation_order: List[str]  # ordered service names for remediation
    failure_injections: List[Dict[str, str]]  # [{service, failure_mode}]


# ──────────────────────── INCIDENT 1: Simple Alert Triage ────────────────────────

INCIDENT_1 = IncidentScenario(
    id=1,
    name="alert_triage",
    description="Database service experiencing high CPU load, causing elevated error rates. Straightforward single-service failure.",
    difficulty="easy",
    alerts=[
        Alert(id="ALT-001", service="db_service", severity_ground_truth="P1",
              title="High CPU usage on db_service",
              description="CPU utilization has exceeded 90% for the past 5 minutes on db_service primary node.",
              timestamp="2026-04-08T03:15:00Z"),
        Alert(id="ALT-002", service="db_service", severity_ground_truth="P2",
              title="Elevated query latency on db_service",
              description="Average query latency increased from 5ms to 25ms in the last 10 minutes.",
              timestamp="2026-04-08T03:16:30Z"),
        Alert(id="ALT-003", service="auth_service", severity_ground_truth="P2",
              title="Increased error rate on auth_service",
              description="Error rate increased to 7% on auth_service. Upstream dependency may be affected.",
              timestamp="2026-04-08T03:17:00Z"),
        Alert(id="ALT-004", service="api_gateway", severity_ground_truth="P3",
              title="Slightly elevated latency on api_gateway",
              description="P95 latency increased by 40% on api_gateway. Within acceptable bounds but trending up.",
              timestamp="2026-04-08T03:18:00Z"),
        Alert(id="ALT-005", service="notification_service", severity_ground_truth="P3",
              title="Notification delivery delay",
              description="Email notifications experiencing 30-second delivery delay. Non-critical service.",
              timestamp="2026-04-08T03:19:00Z"),
    ],
    root_causes=[
        RootCause(service="db_service", failure_mode="cpu_overload",
                  description="Database CPU overload due to unoptimized query pattern",
                  remediation="scale_up"),
    ],
    affected_services=["db_service", "auth_service", "api_gateway"],
    expected_classifications={
        "ALT-001": "P1", "ALT-002": "P2", "ALT-003": "P2",
        "ALT-004": "P3", "ALT-005": "P3",
    },
    expected_routings={},
    expected_remediations=[{"service": "db_service", "action": "scale_up"}],
    remediation_order=["db_service"],
    failure_injections=[{"service": "db_service", "failure_mode": "cpu_overload"}],
)


# ──────────────────────── INCIDENT 2: Cascading Failure ────────────────────────

INCIDENT_2 = IncidentScenario(
    id=2,
    name="root_cause_analysis",
    description="Cascading failure originating from database service disk space exhaustion. Multiple services affected through dependency chain. Requires tracing through the dependency graph to find root cause.",
    difficulty="medium",
    alerts=[
        Alert(id="ALT-101", service="api_gateway", severity_ground_truth="P0",
              title="API Gateway returning 503 errors",
              description="API Gateway returning 503 Service Unavailable for 40% of requests. Customer-facing impact.",
              timestamp="2026-04-08T03:15:00Z"),
        Alert(id="ALT-102", service="order_service", severity_ground_truth="P1",
              title="Order processing failures",
              description="Order creation failing with database connection errors. Revenue impact.",
              timestamp="2026-04-08T03:15:30Z"),
        Alert(id="ALT-103", service="auth_service", severity_ground_truth="P1",
              title="Authentication failures spike",
              description="Login success rate dropped to 60%. Token validation failing intermittently.",
              timestamp="2026-04-08T03:15:45Z"),
        Alert(id="ALT-104", service="db_service", severity_ground_truth="P0",
              title="Database write failures",
              description="PostgreSQL returning ENOSPC errors on write operations. WAL archival stopped.",
              timestamp="2026-04-08T03:14:00Z"),
        Alert(id="ALT-105", service="payment_service", severity_ground_truth="P1",
              title="Payment processing degraded",
              description="Payment confirmations timing out. Retry queue growing.",
              timestamp="2026-04-08T03:16:00Z"),
        Alert(id="ALT-106", service="cache_service", severity_ground_truth="P2",
              title="Cache miss rate increasing",
              description="Cache miss rate increased from 5% to 35%. Falling back to database queries.",
              timestamp="2026-04-08T03:16:30Z"),
        Alert(id="ALT-107", service="notification_service", severity_ground_truth="P3",
              title="Notification queue backlog",
              description="Email/SMS notification queue depth at 15,000. Delivery delayed by 10 minutes.",
              timestamp="2026-04-08T03:17:00Z"),
        Alert(id="ALT-108", service="db_service", severity_ground_truth="P0",
              title="Database disk usage critical",
              description="Disk usage at 99.2% on /data/pgdata volume. Immediate action required.",
              timestamp="2026-04-08T03:13:00Z"),
    ],
    root_causes=[
        RootCause(service="db_service", failure_mode="disk_full",
                  description="Database disk space exhausted due to unarchived WAL logs",
                  remediation="scale_up"),
    ],
    affected_services=["db_service", "auth_service", "order_service", "payment_service", "cache_service", "api_gateway"],
    expected_classifications={
        "ALT-101": "P0", "ALT-102": "P1", "ALT-103": "P1", "ALT-104": "P0",
        "ALT-105": "P1", "ALT-106": "P2", "ALT-107": "P3", "ALT-108": "P0",
    },
    expected_routings={},
    expected_remediations=[{"service": "db_service", "action": "scale_up"}],
    remediation_order=["db_service"],
    failure_injections=[{"service": "db_service", "failure_mode": "disk_full"}],
)


# ──────────────────────── INCIDENT 3: Multi-Root-Cause ────────────────────────

INCIDENT_3 = IncidentScenario(
    id=3,
    name="full_incident_response",
    description="Complex dual-root-cause incident: cache_service has a memory leak AND payment_service has a config error from a recent deployment. Overlapping symptoms make diagnosis challenging. Requires identifying BOTH root causes and executing remediations in dependency-safe order.",
    difficulty="hard",
    alerts=[
        Alert(id="ALT-201", service="api_gateway", severity_ground_truth="P0",
              title="API Gateway error rate critical",
              description="Error rate exceeded 25%. Multiple downstream services reporting failures.",
              timestamp="2026-04-08T03:20:00Z"),
        Alert(id="ALT-202", service="cache_service", severity_ground_truth="P1",
              title="Cache service memory critical",
              description="Redis memory usage at 96%. Eviction rate spiking. OOM kill risk.",
              timestamp="2026-04-08T03:18:00Z"),
        Alert(id="ALT-203", service="payment_service", severity_ground_truth="P0",
              title="Payment service connection failures",
              description="All payment processing failing. 100% error rate on Stripe API calls.",
              timestamp="2026-04-08T03:19:00Z"),
        Alert(id="ALT-204", service="order_service", severity_ground_truth="P0",
              title="Order creation completely blocked",
              description="Order service returning 500 for all new orders. Both payment and cache dependencies failing.",
              timestamp="2026-04-08T03:20:30Z"),
        Alert(id="ALT-205", service="cache_service", severity_ground_truth="P1",
              title="Cache corruption detected",
              description="Checksum mismatches on cached session data. Stale data being served to auth_service.",
              timestamp="2026-04-08T03:19:30Z"),
        Alert(id="ALT-206", service="auth_service", severity_ground_truth="P1",
              title="Session validation failures",
              description="Valid sessions being rejected due to corrupted cache entries.",
              timestamp="2026-04-08T03:20:00Z"),
        Alert(id="ALT-207", service="payment_service", severity_ground_truth="P0",
              title="Payment service TLS certificate mismatch",
              description="TLS handshake failing to payment gateway. Recent config change suspected.",
              timestamp="2026-04-08T03:19:15Z"),
        Alert(id="ALT-208", service="db_service", severity_ground_truth="P2",
              title="Database connection pool saturation",
              description="Connection pool at 95% capacity due to cache misses causing direct DB queries.",
              timestamp="2026-04-08T03:21:00Z"),
        Alert(id="ALT-209", service="notification_service", severity_ground_truth="P2",
              title="Notification failures for order confirmations",
              description="Cannot send order confirmation emails — order data unavailable.",
              timestamp="2026-04-08T03:21:30Z"),
        Alert(id="ALT-210", service="cache_service", severity_ground_truth="P1",
              title="Redis out-of-memory warnings",
              description="Redis: 'WARNING: OOM command not allowed when used memory > maxmemory'",
              timestamp="2026-04-08T03:18:30Z"),
        Alert(id="ALT-211", service="api_gateway", severity_ground_truth="P1",
              title="API Gateway circuit breaker tripped",
              description="Circuit breaker OPEN for order_service and payment_service routes.",
              timestamp="2026-04-08T03:21:00Z"),
        Alert(id="ALT-212", service="order_service", severity_ground_truth="P1",
              title="Order service retry storm",
              description="Retry queue at 50,000 entries. Exponential backoff not preventing cascade.",
              timestamp="2026-04-08T03:22:00Z"),
    ],
    root_causes=[
        RootCause(service="cache_service", failure_mode="memory_leak",
                  description="Redis memory leak from uncleared session objects after recent deployment",
                  remediation="restart_service"),
        RootCause(service="payment_service", failure_mode="config_error",
                  description="Bad TLS certificate path in payment gateway config from 03:15 deployment",
                  remediation="rollback_config"),
    ],
    affected_services=["cache_service", "payment_service", "auth_service", "order_service", "api_gateway", "db_service"],
    expected_classifications={
        "ALT-201": "P0", "ALT-202": "P1", "ALT-203": "P0", "ALT-204": "P0",
        "ALT-205": "P1", "ALT-206": "P1", "ALT-207": "P0", "ALT-208": "P2",
        "ALT-209": "P2", "ALT-210": "P1", "ALT-211": "P1", "ALT-212": "P1",
    },
    expected_routings={},
    expected_remediations=[
        {"service": "cache_service", "action": "restart_service"},
        {"service": "payment_service", "action": "rollback_config"},
    ],
    # Cache first (auth_service depends on it), then payment
    remediation_order=["cache_service", "payment_service"],
    failure_injections=[
        {"service": "cache_service", "failure_mode": "memory_leak"},
        {"service": "payment_service", "failure_mode": "config_error"},
    ],
)


# ──────────────────────── Registry ────────────────────────

INCIDENTS = {
    1: INCIDENT_1,
    2: INCIDENT_2,
    3: INCIDENT_3,
}

INCIDENT_BY_NAME = {
    "alert_triage": INCIDENT_1,
    "root_cause_analysis": INCIDENT_2,
    "full_incident_response": INCIDENT_3,
}
