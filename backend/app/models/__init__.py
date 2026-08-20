"""Model package.

Every model module must be imported here: Alembic autogenerate only sees the
tables that have been registered on Base.metadata by import time.
"""

from app.models.base import Base
from app.models.category import Category
from app.models.course import Course
from app.models.refresh_token import RefreshToken
from app.models.user import User

__all__ = ["Base", "Category", "Course", "RefreshToken", "User"]
