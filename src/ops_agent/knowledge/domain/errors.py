"""Transport-independent Knowledge module errors."""


class KnowledgeError(RuntimeError):
    code = "KNOWLEDGE_ERROR"
    retryable = False


class KnowledgeDisabledError(KnowledgeError):
    code = "KNOWLEDGE_DISABLED"


class KnowledgeDependencyError(KnowledgeError):
    code = "KNOWLEDGE_DEPENDENCY_ERROR"
    retryable = True


class KnowledgeResolutionError(KnowledgeError):
    """The requested product scope cannot be resolved deterministically."""

    code = "KNOWLEDGE_RESOLUTION_ERROR"


class UnknownProductError(KnowledgeResolutionError):
    code = "KNOWLEDGE_PRODUCT_NOT_INSTALLED"


class UnknownProductVersionError(KnowledgeResolutionError):
    code = "KNOWLEDGE_PRODUCT_VERSION_NOT_INSTALLED"


class InvalidProductSkillError(KnowledgeError):
    """An installed plugin payload is malformed or contradicts its manifest."""

    code = "KNOWLEDGE_PLUGIN_INVALID"
