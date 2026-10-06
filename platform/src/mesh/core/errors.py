"""Domain exceptions. Catch-all handlers must re-raise or convert to one of these."""


class MeshError(Exception):
    """Base class for every platform error."""


class InfraFailure(MeshError):
    """Failure not caused by the agent (tunnel down, OOM-kill, container start timeout).

    Never consumes a task attempt.
    """


class TaskFailure(MeshError):
    """The agent's work failed a check. Consumes a task attempt."""


class PolicyViolation(MeshError):
    """Protected-path edit, scope violation, skip/xfail added, suppression growth."""


class BudgetExceeded(MeshError):
    """A context, token or GPU budget was exceeded (rejected, never truncated)."""


class GateMismatch(MeshError):
    """A gate decision does not match the hash of the gate package. Fail closed."""
