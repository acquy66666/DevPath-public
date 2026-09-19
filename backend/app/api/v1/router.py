from fastapi import APIRouter

from app.api.v1 import (
    auth,
    categories,
    chat,
    courses,
    curriculum,
    enrollments,
    grading,
    health,
    progress,
    quiz,
    recommendations,
    reviews,
    study,
    users,
    video,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(chat.router)
api_router.include_router(courses.router)
api_router.include_router(curriculum.router)
api_router.include_router(enrollments.router)
api_router.include_router(grading.router)
api_router.include_router(progress.router)
api_router.include_router(quiz.router)
api_router.include_router(recommendations.router)
api_router.include_router(reviews.router)
api_router.include_router(study.router)
api_router.include_router(video.router)
