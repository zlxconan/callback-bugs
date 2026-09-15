"""Transport-independent Knowledge module errors."""


class KnowledgeError(RuntimeError):
    code = "KNOWLEDGE_ERROR"
    retryable = False


class KnowledgeDisabledError(KnowledgeError):
    code = "KNOWLEDGE_DISABLED"


class KnowledgeDependencyError(KnowledgeError):
    code = "KNOWLEDGE_DEPENDENCY_ERROR"
    retryable = True
