"""Transport-independent Reproduction module errors."""


class ReproductionError(RuntimeError):
    code = "REPRODUCTION_ERROR"
    retryable = False


class ReproductionDisabledError(ReproductionError):
    code = "REPRODUCTION_DISABLED"


class ReproductionDependencyError(ReproductionError):
    code = "REPRODUCTION_DEPENDENCY_ERROR"
    retryable = True
