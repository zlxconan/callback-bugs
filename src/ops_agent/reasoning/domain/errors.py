"""Transport-independent Reasoning module errors."""


class ReasoningError(RuntimeError):
    code = "REASONING_ERROR"
    retryable = False


class ReasoningDisabledError(ReasoningError):
    code = "REASONING_DISABLED"


class ReasoningDependencyError(ReasoningError):
    code = "REASONING_DEPENDENCY_ERROR"
    retryable = True
