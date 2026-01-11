class KaidfGenError(Exception):
    """Base error for kaidf_gen."""


class SpecValidationError(KaidfGenError):
    """Raised when the spec does not validate."""


class GenerationError(KaidfGenError):
    """Raised when generation fails."""


class TemplateNotFoundError(KaidfGenError):
    """Raised when a referenced template key is missing."""


class UnsafePathError(KaidfGenError):
    """Raised when a path tries to escape the output directory."""
