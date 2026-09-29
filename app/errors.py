"""Domain errors raised by the service layer.

Services raise these to describe *what went wrong in the domain* — an entity
was absent, a value collided with an existing one. They never mention HTTP.
The mapping onto status codes happens once, in the exception handlers
registered by the app factory, which read `status_code` off the instance.
"""


class ApiError(Exception):
    """Base class for every error the application raises deliberately.

    A single handler catches this type, so any subclass is translated into the
    standard error envelope without further registration.
    """

    status_code: int = 500
    message: str = "Something went wrong"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.__class__.message
        super().__init__(self.message)


class BadRequestError(ApiError):
    """The request is malformed in a way the schema layer cannot express."""

    status_code = 400
    message = "Bad request"


class NotFoundError(ApiError):
    """The entity does not exist, or belongs to another host.

    Both cases produce the same error on purpose: a row owned by someone else
    must be indistinguishable from one that was never there.
    """

    status_code = 404
    message = "Not found"


class ConflictError(ApiError):
    """The request collides with something already stored."""

    status_code = 409
    message = "Conflict"


# --- Factory helpers ---------------------------------------------------
# Keep wording consistent across services, so twelve call sites do not
# produce twelve slightly different phrasings of the same failure.


def not_found(entity: str) -> NotFoundError:
    """`not_found("User")` -> "User not found"."""
    return NotFoundError(f"{entity} not found")


def already_exists(what: str) -> ConflictError:
    """`already_exists("Email")` -> "Email already in use"."""
    return ConflictError(f"{what} already in use")


def slug_taken() -> ConflictError:
    """The (hostId, slug) pair is already claimed by another event type."""
    return ConflictError("Slug already in use for this host")