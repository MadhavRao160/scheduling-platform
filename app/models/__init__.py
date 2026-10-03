"""Importing this package imports every model, so that each one registers
itself on Base.metadata. Alembic relies on that: a model never imported is a
table it cannot see, and autogenerate would silently skip it."""

from app.models.base import Base
from app.models.user import User

__all__ = ["Base", "User"]