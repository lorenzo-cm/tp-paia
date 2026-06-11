class RepositoryError(Exception):
    """Base repository exception."""


class RepositoryNotFoundError(RepositoryError):
    """Raised when an entity is not found."""


class RepositoryCreationError(RepositoryError):
    """Raised when entity creation fails."""


class RepositoryUpdateError(RepositoryError):
    """Raised when entity update fails."""


class RepositoryDeleteError(RepositoryError):
    """Raised when entity deletion fails."""
