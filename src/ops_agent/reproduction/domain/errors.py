"""Transport-independent Reproduction module errors."""


class ReproductionError(RuntimeError):
    code = "REPRODUCTION_ERROR"
    retryable = False


class ReproductionDisabledError(ReproductionError):
    code = "REPRODUCTION_DISABLED"


class ReproductionDependencyError(ReproductionError):
    code = "REPRODUCTION_DEPENDENCY_ERROR"
    retryable = True


class ReproductionPolicyError(ReproductionError):
    code = "REPRODUCTION_POLICY_REJECTED"


class ReproductionTimeoutError(ReproductionDependencyError):
    code = "REPRODUCTION_TOOL_TIMEOUT"
