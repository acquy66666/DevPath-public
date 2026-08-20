"""Shared FastAPI dependencies.

Auth dependencies (get_current_user, require_role) land here in Phase 2.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]

__all__ = ["DbSession", "get_db"]
