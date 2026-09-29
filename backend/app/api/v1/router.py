from fastapi import APIRouter

from app.api.v1 import (
    auth,
    categories,
    certificates,
    chat,
    commerce,
    courses,
    curriculum,
    enrollments,
    gamification,
    grading,
    health,
    instructor,
    leaderboard,
    orders,
    payments,
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
api_router.include_router(certificates.router)
api_router.include_router(chat.router)
api_router.include_router(commerce.router)
api_router.include_router(courses.router)
api_router.include_router(curriculum.router)
api_router.include_router(enrollments.router)
api_router.include_router(gamification.router)
api_router.include_router(grading.router)
api_router.include_router(instructor.router)
api_router.include_router(leaderboard.router)
api_router.include_router(orders.router)
api_router.include_router(payments.router)
api_router.include_router(progress.router)
api_router.include_router(quiz.router)
api_router.include_router(recommendations.router)
api_router.include_router(reviews.router)
api_router.include_router(study.router)
api_router.include_router(video.router)
