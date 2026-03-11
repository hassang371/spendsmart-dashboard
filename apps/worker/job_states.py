from enum import Enum


class JobStatus(str, Enum):
    """Lifecycle states for background jobs."""

    PENDING = "pending"
    CLAIMED = "claimed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class InvalidTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""

    pass


# Strict state machine defining allowed (from -> to) transitions
VALID_TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.CLAIMED, JobStatus.PROCESSING, JobStatus.FAILED},
    JobStatus.CLAIMED: {JobStatus.PROCESSING, JobStatus.FAILED},
    JobStatus.PROCESSING: {JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),  # Terminal state
    JobStatus.FAILED: {JobStatus.PENDING},  # Retry allowed
}


def transition(current_state: str, next_state: str) -> None:
    """Validate a state transition based on the strict state machine."""
    try:
        current = JobStatus(current_state)
        nxt = JobStatus(next_state)
    except ValueError:
        raise InvalidTransitionError(f"Invalid state values: {current_state} -> {next_state}")

    if nxt not in VALID_TRANSITIONS.get(current, set()):
        raise InvalidTransitionError(f"Illegal job transition: {current_state} -> {next_state}")
