"""
Deterministic Grading Engine for IncidentResponseEnv.

Produces scores between 0.0 and 1.0 based on agent actions vs ground truth.
Fully reproducible — no randomness in grading logic.
"""

from typing import Dict, List, Optional, Tuple
try:
    from .incidents import IncidentScenario, INCIDENTS
    from .tasks import TaskConfig, TASKS
except ImportError:
    from incidents import IncidentScenario, INCIDENTS
    from tasks import TaskConfig, TASKS


class Grader:
    """Deterministic grader that scores agent performance on incident response tasks."""

    def __init__(self, task_config: TaskConfig, incident: IncidentScenario):
        self.task = task_config
        self.incident = incident

        # Track agent actions
        self.classifications: Dict[str, str] = {}  # alert_id -> severity
        self.root_causes: List[Dict[str, str]] = []  # [{service, failure_mode}]
        self.remediations: List[Dict[str, str]] = []  # [{service, action}] in order
        self.identified_affected: List[str] = []  # service names

        # Track penalties
        self.invalid_actions: int = 0
        self.wrong_remediations: int = 0
        self.steps_taken: int = 0

    def record_classification(self, alert_id: str, severity: str) -> Tuple[float, str]:
        """Record an alert classification and return immediate reward."""
        expected = self.incident.expected_classifications.get(alert_id)
        if expected is None:
            self.invalid_actions += 1
            return -0.5, f"Invalid alert ID: {alert_id}"

        self.classifications[alert_id] = severity
        if severity == expected:
            return 1.0, f"Correct! Alert {alert_id} is {severity}"
        else:
            return -0.3, f"Incorrect. Alert {alert_id} classified as {severity}, expected {expected}"

    def record_root_cause(self, service: str, failure_mode: str) -> Tuple[float, str]:
        """Record a root cause identification and return immediate reward."""
        self.root_causes.append({"service": service, "failure_mode": failure_mode})

        for rc in self.incident.root_causes:
            if rc.service == service and rc.failure_mode == failure_mode:
                return 3.0, f"Correct root cause: {service} ({failure_mode})"
            elif rc.service == service:
                return 0.5, f"Correct service ({service}) but wrong failure mode. Expected: {rc.failure_mode}"

        return -1.0, f"Incorrect root cause: {service} is not a root cause of this incident"

    def record_remediation(self, service: str, action: str) -> Tuple[float, str]:
        """Record a remediation action and return immediate reward."""
        self.remediations.append({"service": service, "action": action})

        for expected in self.incident.expected_remediations:
            if expected["service"] == service and expected["action"] == action:
                # Check order bonus
                expected_idx = self.incident.remediation_order.index(service)
                actual_idx = len(self.remediations) - 1
                order_bonus = 1.0 if actual_idx == expected_idx else 0.0
                return 2.0 + order_bonus, f"Correct remediation: {action} on {service}" + (" (correct order!)" if order_bonus else "")
            elif expected["service"] == service:
                self.wrong_remediations += 1
                return -1.5, f"Wrong remediation for {service}. Applied '{action}', expected '{expected['action']}'"

        self.wrong_remediations += 1
        return -1.5, f"Unnecessary remediation: {service} does not need {action}"

    def record_step(self):
        """Record a step taken."""
        self.steps_taken += 1

    def compute_final_score(self) -> Dict:
        """Compute the final normalized score (0.0 to 1.0) with breakdown."""
        scores = {}
        weights = self.task.grading_weights

        # Classification accuracy
        if "classification" in weights:
            expected = self.incident.expected_classifications
            if len(expected) == 0:
                scores["classification"] = 1.0
            else:
                correct = sum(
                    1 for aid, sev in self.classifications.items()
                    if expected.get(aid) == sev
                )
                scores["classification"] = correct / len(expected)

        # Root cause accuracy
        if "root_cause" in weights:
            expected_rcs = self.incident.root_causes
            if len(expected_rcs) == 0:
                scores["root_cause"] = 1.0
            else:
                correct_rcs = 0
                for rc in expected_rcs:
                    for agent_rc in self.root_causes:
                        if agent_rc["service"] == rc.service and agent_rc["failure_mode"] == rc.failure_mode:
                            correct_rcs += 1
                            break
                scores["root_cause"] = correct_rcs / len(expected_rcs)

        # Affected services identification
        if "affected_services" in weights:
            expected_affected = set(self.incident.affected_services)
            if len(expected_affected) == 0:
                scores["affected_services"] = 1.0
            else:
                identified = set(self.identified_affected)
                correct = len(identified & expected_affected)
                false_positives = len(identified - expected_affected)
                precision = correct / max(len(identified), 1)
                recall = correct / len(expected_affected)
                if precision + recall > 0:
                    scores["affected_services"] = 2 * precision * recall / (precision + recall)  # F1
                else:
                    scores["affected_services"] = 0.0

        # Remediation accuracy
        if "remediation" in weights:
            expected_rems = self.incident.expected_remediations
            if len(expected_rems) == 0:
                scores["remediation"] = 1.0
            else:
                correct_rems = 0
                for er in expected_rems:
                    for ar in self.remediations:
                        if ar["service"] == er["service"] and ar["action"] == er["action"]:
                            correct_rems += 1
                            break
                scores["remediation"] = correct_rems / len(expected_rems)

        # Remediation order score
        if "order" in weights:
            expected_order = self.incident.remediation_order
            if len(expected_order) <= 1:
                scores["order"] = 1.0
            else:
                # Check if remediations were done in correct order
                agent_order = [r["service"] for r in self.remediations if r["service"] in expected_order]
                # Remove duplicates while preserving order
                seen = set()
                agent_order_dedup = []
                for s in agent_order:
                    if s not in seen:
                        seen.add(s)
                        agent_order_dedup.append(s)

                if agent_order_dedup == expected_order:
                    scores["order"] = 1.0
                elif len(agent_order_dedup) == len(expected_order):
                    scores["order"] = 0.3  # All done but wrong order
                else:
                    scores["order"] = 0.0

        # Compute weighted final score
        weighted_score = sum(
            scores.get(key, 0.0) * weight
            for key, weight in weights.items()
        )

        # Apply penalties
        penalty = (
            self.invalid_actions * 0.05 +
            max(0, self.steps_taken - self.task.max_steps * 0.7) * 0.02
        )
        final_score = max(0.0, min(1.0, weighted_score - penalty))

        return {
            "final_score": round(final_score, 4),
            "component_scores": {k: round(v, 4) for k, v in scores.items()},
            "penalties": {
                "invalid_actions": self.invalid_actions,
                "wrong_remediations": self.wrong_remediations,
                "steps_taken": self.steps_taken,
                "total_penalty": round(penalty, 4),
            },
            "task": self.task.name,
            "difficulty": self.task.difficulty,
        }
