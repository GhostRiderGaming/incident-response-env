"""
Simulated Microservices Infrastructure.

Models a production system with 7 microservices, dependency graph,
health metrics, log generation, and deterministic failure injection.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta


# ──────────────────────── Service Definitions ────────────────────────

SERVICE_DEFINITIONS = {
    "api_gateway": {
        "display_name": "API Gateway",
        "dependencies": ["auth_service", "order_service"],
        "base_metrics": {"cpu_percent": 25.0, "memory_percent": 40.0, "error_rate_percent": 0.1, "latency_ms": 45, "requests_per_sec": 1200},
        "description": "Entry point for all client requests. Routes to internal services.",
    },
    "auth_service": {
        "display_name": "Authentication Service",
        "dependencies": ["db_service"],
        "base_metrics": {"cpu_percent": 15.0, "memory_percent": 30.0, "error_rate_percent": 0.05, "latency_ms": 20, "requests_per_sec": 800},
        "description": "Handles JWT token validation, OAuth flows, and session management.",
    },
    "order_service": {
        "display_name": "Order Service",
        "dependencies": ["db_service", "payment_service", "notification_service"],
        "base_metrics": {"cpu_percent": 35.0, "memory_percent": 50.0, "error_rate_percent": 0.2, "latency_ms": 80, "requests_per_sec": 500},
        "description": "Manages order lifecycle: creation, processing, fulfillment.",
    },
    "db_service": {
        "display_name": "Database Service",
        "dependencies": [],
        "base_metrics": {"cpu_percent": 40.0, "memory_percent": 60.0, "error_rate_percent": 0.01, "latency_ms": 5, "requests_per_sec": 3000},
        "description": "PostgreSQL primary + read replicas. Handles all persistent storage.",
    },
    "payment_service": {
        "display_name": "Payment Service",
        "dependencies": ["db_service"],
        "base_metrics": {"cpu_percent": 20.0, "memory_percent": 35.0, "error_rate_percent": 0.1, "latency_ms": 150, "requests_per_sec": 200},
        "description": "Processes payments via Stripe/PayPal. PCI-DSS compliant.",
    },
    "notification_service": {
        "display_name": "Notification Service",
        "dependencies": [],
        "base_metrics": {"cpu_percent": 10.0, "memory_percent": 20.0, "error_rate_percent": 0.05, "latency_ms": 30, "requests_per_sec": 400},
        "description": "Sends emails, push notifications, and SMS alerts.",
    },
    "cache_service": {
        "display_name": "Cache Service (Redis)",
        "dependencies": ["db_service"],
        "base_metrics": {"cpu_percent": 12.0, "memory_percent": 45.0, "error_rate_percent": 0.02, "latency_ms": 2, "requests_per_sec": 5000},
        "description": "Redis cluster for session caching, rate limiting, and query caching.",
    },
}

DEPENDENCY_GRAPH = {
    name: defn["dependencies"] for name, defn in SERVICE_DEFINITIONS.items()
}


# ──────────────────────── Failure Modes ────────────────────────

FAILURE_MODES = {
    "cpu_overload": {
        "description": "CPU utilization spiked to critical levels",
        "metric_effects": {"cpu_percent": 95.0, "latency_ms": "5x", "error_rate_percent": 15.0},
        "remediation": "scale_up",
    },
    "memory_leak": {
        "description": "Memory usage growing unbounded due to leak",
        "metric_effects": {"memory_percent": 97.0, "latency_ms": "3x", "error_rate_percent": 8.0},
        "remediation": "restart_service",
    },
    "config_error": {
        "description": "Bad configuration deployed causing connection failures",
        "metric_effects": {"error_rate_percent": 45.0, "latency_ms": "10x"},
        "remediation": "rollback_config",
    },
    "disk_full": {
        "description": "Disk space exhausted on database volume",
        "metric_effects": {"error_rate_percent": 60.0, "latency_ms": "8x", "cpu_percent": 80.0},
        "remediation": "scale_up",
    },
    "cache_corruption": {
        "description": "Cache entries corrupted causing stale data returns",
        "metric_effects": {"error_rate_percent": 25.0, "latency_ms": "2x"},
        "remediation": "clear_cache",
    },
    "network_partition": {
        "description": "Network connectivity lost between services",
        "metric_effects": {"error_rate_percent": 70.0, "latency_ms": "20x"},
        "remediation": "restart_service",
    },
}


# ──────────────────────── Log Templates ────────────────────────

HEALTHY_LOG_TEMPLATES = [
    "{timestamp} INFO  [{service}] Request processed successfully in {latency}ms",
    "{timestamp} INFO  [{service}] Health check passed - all systems nominal",
    "{timestamp} DEBUG [{service}] Connection pool: {pool_active}/50 active",
    "{timestamp} INFO  [{service}] Metrics exported to monitoring pipeline",
    "{timestamp} DEBUG [{service}] Cache hit ratio: {cache_hit}%",
]

ERROR_LOG_TEMPLATES = {
    "cpu_overload": [
        "{timestamp} WARN  [{service}] CPU usage at {cpu}% - approaching threshold",
        "{timestamp} ERROR [{service}] Request timeout after {timeout}ms - thread pool exhausted",
        "{timestamp} WARN  [{service}] GC pause detected: {gc_pause}ms. Heap pressure critical",
        "{timestamp} ERROR [{service}] Circuit breaker OPEN - too many timeouts",
        "{timestamp} CRIT  [{service}] Service degraded: latency p99={p99}ms (normal: {normal_p99}ms)",
    ],
    "memory_leak": [
        "{timestamp} WARN  [{service}] Heap usage at {memory}% - growing trend detected",
        "{timestamp} ERROR [{service}] OutOfMemoryError: unable to allocate {alloc_mb}MB",
        "{timestamp} WARN  [{service}] GC overhead limit exceeded - {gc_overhead}% time in GC",
        "{timestamp} ERROR [{service}] Object pool exhausted, {leaked_count} unreleased connections",
        "{timestamp} CRIT  [{service}] Memory usage critical: {memory}% - OOM kill imminent",
    ],
    "config_error": [
        "{timestamp} ERROR [{service}] Failed to connect to upstream: connection refused",
        "{timestamp} ERROR [{service}] Invalid configuration key 'database.primary.host': null",
        "{timestamp} WARN  [{service}] Falling back to default config - primary config invalid",
        "{timestamp} ERROR [{service}] TLS handshake failed: certificate mismatch for {host}",
        "{timestamp} CRIT  [{service}] Service startup failed: config validation error in {config_file}",
    ],
    "disk_full": [
        "{timestamp} ERROR [{service}] Write failed: No space left on device",
        "{timestamp} CRIT  [{service}] WAL log write failed - disk full on /data/pgdata",
        "{timestamp} ERROR [{service}] Cannot create temporary file for sort operation",
        "{timestamp} WARN  [{service}] Disk usage at {disk}% on volume /data",
        "{timestamp} ERROR [{service}] Transaction log archival failed: ENOSPC",
    ],
    "cache_corruption": [
        "{timestamp} WARN  [{service}] Cache checksum mismatch for key session:{session_id}",
        "{timestamp} ERROR [{service}] Deserialization failed: corrupted entry in slot {slot}",
        "{timestamp} WARN  [{service}] Stale data detected - cache TTL inconsistency",
        "{timestamp} ERROR [{service}] Redis DUMP/RESTORE failed: payload integrity check failed",
        "{timestamp} WARN  [{service}] Cache eviction storm: {evicted_count} keys evicted in {window}s",
    ],
    "network_partition": [
        "{timestamp} ERROR [{service}] Connection to {target} timed out after {timeout}ms",
        "{timestamp} CRIT  [{service}] Lost connectivity to {count} downstream services",
        "{timestamp} ERROR [{service}] DNS resolution failed for {target}.internal",
        "{timestamp} WARN  [{service}] Retrying connection to {target} (attempt {attempt}/5)",
        "{timestamp} ERROR [{service}] TCP RST received from {target} - connection reset",
    ],
}


# ──────────────────────── Infrastructure State ────────────────────────

@dataclass
class ServiceState:
    """Current state of a single service."""
    name: str
    status: str = "healthy"  # healthy, degraded, down
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    error_rate_percent: float = 0.0
    latency_ms: int = 0
    requests_per_sec: int = 0
    failure_mode: Optional[str] = None
    is_root_cause: bool = False


@dataclass
class InfrastructureState:
    """Complete state of the simulated infrastructure."""
    services: Dict[str, ServiceState] = field(default_factory=dict)
    rng: random.Random = field(default_factory=lambda: random.Random(42))
    base_time: datetime = field(default_factory=lambda: datetime(2026, 4, 8, 3, 15, 0))

    def reset_to_healthy(self, seed: int = 42):
        """Reset all services to healthy baseline."""
        self.rng = random.Random(seed)
        self.services = {}
        for name, defn in SERVICE_DEFINITIONS.items():
            metrics = defn["base_metrics"]
            self.services[name] = ServiceState(
                name=name,
                status="healthy",
                cpu_percent=metrics["cpu_percent"] + self.rng.uniform(-3, 3),
                memory_percent=metrics["memory_percent"] + self.rng.uniform(-2, 2),
                error_rate_percent=metrics["error_rate_percent"],
                latency_ms=int(metrics["latency_ms"] * self.rng.uniform(0.8, 1.2)),
                requests_per_sec=int(metrics["requests_per_sec"] * self.rng.uniform(0.9, 1.1)),
            )

    def inject_failure(self, service_name: str, failure_mode: str, is_root_cause: bool = True):
        """Inject a failure into a service and cascade to dependents."""
        if service_name not in self.services:
            return
        if failure_mode not in FAILURE_MODES:
            return

        svc = self.services[service_name]
        fm = FAILURE_MODES[failure_mode]
        effects = fm["metric_effects"]

        # Apply direct effects
        if "cpu_percent" in effects:
            svc.cpu_percent = effects["cpu_percent"]
        if "memory_percent" in effects:
            svc.memory_percent = effects["memory_percent"]
        if "error_rate_percent" in effects:
            svc.error_rate_percent = effects["error_rate_percent"]
        if "latency_ms" in effects:
            val = effects["latency_ms"]
            if isinstance(val, str) and val.endswith("x"):
                multiplier = int(val.replace("x", ""))
                base = SERVICE_DEFINITIONS[service_name]["base_metrics"]["latency_ms"]
                svc.latency_ms = base * multiplier
            else:
                svc.latency_ms = int(val)

        svc.failure_mode = failure_mode
        svc.is_root_cause = is_root_cause

        # Set status based on error rate
        if svc.error_rate_percent > 30:
            svc.status = "down"
        elif svc.error_rate_percent > 5:
            svc.status = "degraded"

        # Cascade to dependent services
        self._cascade_failure(service_name)

    def _cascade_failure(self, failed_service: str):
        """Propagate degradation to services that depend on the failed one."""
        for svc_name, deps in DEPENDENCY_GRAPH.items():
            if failed_service in deps and svc_name != failed_service:
                svc = self.services[svc_name]
                if svc.failure_mode is not None:
                    continue  # Already has its own failure, skip
                failed = self.services[failed_service]

                # Cascade effects: increase error rate and latency proportionally
                cascade_error = min(failed.error_rate_percent * 0.5, 40.0)
                cascade_latency_mult = 1.5 if failed.status == "degraded" else 3.0

                svc.error_rate_percent = max(svc.error_rate_percent, cascade_error)
                base_latency = SERVICE_DEFINITIONS[svc_name]["base_metrics"]["latency_ms"]
                svc.latency_ms = max(svc.latency_ms, int(base_latency * cascade_latency_mult))
                svc.cpu_percent = min(svc.cpu_percent + 15, 90.0)

                if svc.error_rate_percent > 20:
                    svc.status = "degraded"
                elif svc.error_rate_percent > 5:
                    svc.status = "degraded"

    def generate_logs(self, service_name: str, num_lines: int = 20) -> List[str]:
        """Generate realistic log lines for a service."""
        if service_name not in self.services:
            return [f"ERROR: Service '{service_name}' not found"]

        svc = self.services[service_name]
        logs = []

        for i in range(num_lines):
            ts = (self.base_time + timedelta(seconds=i * 2)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            if svc.failure_mode and self.rng.random() < 0.6:
                # Error logs
                templates = ERROR_LOG_TEMPLATES.get(svc.failure_mode, HEALTHY_LOG_TEMPLATES)
                template = self.rng.choice(templates)
                log_line = template.format(
                    timestamp=ts,
                    service=svc.name,
                    cpu=f"{svc.cpu_percent:.1f}",
                    memory=f"{svc.memory_percent:.1f}",
                    timeout=svc.latency_ms * 3,
                    gc_pause=self.rng.randint(200, 2000),
                    p99=svc.latency_ms * 5,
                    normal_p99=SERVICE_DEFINITIONS[service_name]["base_metrics"]["latency_ms"] * 2,
                    alloc_mb=self.rng.randint(256, 2048),
                    gc_overhead=self.rng.randint(60, 95),
                    leaked_count=self.rng.randint(50, 500),
                    host=f"{self.rng.choice(['db-primary', 'cache-01', 'auth-02'])}.internal",
                    config_file=self.rng.choice(["application.yml", "db-config.json", "security.properties"]),
                    disk=self.rng.randint(95, 100),
                    session_id=f"{self.rng.randint(1000,9999)}",
                    slot=self.rng.randint(0, 16383),
                    evicted_count=self.rng.randint(1000, 50000),
                    window=self.rng.randint(1, 10),
                    target=self.rng.choice(DEPENDENCY_GRAPH.get(service_name) or ["internal_process"]),
                    count=self.rng.randint(1, 4),
                    attempt=self.rng.randint(1, 5),
                    latency=svc.latency_ms,
                )
            elif svc.status == "degraded" and self.rng.random() < 0.3:
                # Degraded cascade logs
                log_line = f"{ts} WARN  [{svc.name}] Elevated error rate: {svc.error_rate_percent:.1f}% (upstream dependency degraded)"
            else:
                # Healthy logs
                template = self.rng.choice(HEALTHY_LOG_TEMPLATES)
                log_line = template.format(
                    timestamp=ts,
                    service=svc.name,
                    latency=self.rng.randint(1, svc.latency_ms),
                    pool_active=self.rng.randint(5, 30),
                    cache_hit=self.rng.randint(85, 99),
                )
            logs.append(log_line)

        return logs

    def get_metrics_timeseries(self, service_name: str, metric: str, points: int = 10) -> List[Dict]:
        """Generate a time-series of metric values."""
        if service_name not in self.services:
            return []

        svc = self.services[service_name]
        current_val = getattr(svc, metric, None)
        if current_val is None:
            return []

        data = []
        base = SERVICE_DEFINITIONS[service_name]["base_metrics"].get(metric, current_val)

        for i in range(points):
            ts = (self.base_time - timedelta(minutes=(points - i) * 5)).isoformat()
            if i < points - 3:
                # Historical: near baseline
                val = base + self.rng.uniform(-base * 0.1, base * 0.1)
            else:
                # Recent: trending toward current (failure) value
                progress = (i - (points - 3)) / 3
                val = base + (current_val - base) * progress
            data.append({"timestamp": ts, "value": round(val, 2)})

        return data

    def get_dependency_map(self) -> Dict[str, List[str]]:
        """Return the service dependency graph."""
        return dict(DEPENDENCY_GRAPH)

    def get_service_info(self, service_name: str) -> Optional[Dict]:
        """Get comprehensive info about a service."""
        if service_name not in self.services:
            return None
        svc = self.services[service_name]
        defn = SERVICE_DEFINITIONS[service_name]
        return {
            "name": svc.name,
            "display_name": defn["display_name"],
            "description": defn["description"],
            "status": svc.status,
            "dependencies": defn["dependencies"],
            "metrics": {
                "cpu_percent": round(svc.cpu_percent, 1),
                "memory_percent": round(svc.memory_percent, 1),
                "error_rate_percent": round(svc.error_rate_percent, 2),
                "latency_ms": svc.latency_ms,
                "requests_per_sec": svc.requests_per_sec,
            },
        }
