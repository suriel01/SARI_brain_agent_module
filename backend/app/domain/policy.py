"""Alert policy: when a detection raises the alarm and how loudly it is logged."""

SIREN_CONFIDENCE_THRESHOLD = 0.70


def should_raise_alarm(event_type: str, confidence: float, threshold: float = SIREN_CONFIDENCE_THRESHOLD) -> bool:
    """Only an intrusion at or above the confidence threshold sounds the siren."""
    return event_type == "intrusion" and confidence >= threshold


def alert_log_level(event_type: str, severity: str) -> str:
    if severity == "high" or event_type == "intrusion":
        return "ERROR"
    return "WARN" if severity == "medium" else "INFO"
