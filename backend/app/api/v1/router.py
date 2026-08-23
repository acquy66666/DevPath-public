from fastapi import APIRouter

from app.api.v1 import (
    auth,
    categories,
    courses,
    curriculum,
    enrollments,
    health,
    progress,
    users,
    video,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(courses.router)
api_router.include_router(curriculum.router)
api_router.include_router(enrollments.router)
api_router.include_router(progress.router)
api_router.include_router(video.router)
