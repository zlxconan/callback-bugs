"""Transport-independent Investigation module errors."""


class InvestigationError(RuntimeError):
    code = "INVESTIGATION_ERROR"
    retryable = False


class InvestigationDisabledError(InvestigationError):
    code = "INVESTIGATION_DISABLED"


class InvestigationDependencyError(InvestigationError):
    code = "INVESTIGATION_DEPENDENCY_ERROR"
    retryable = True
