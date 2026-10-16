"""The admin's screens: course review queue, accounts, reports.

Every route requires `role='admin'` and nothing else -- there is no ownership
to check, the admin acts on the whole platform. The rules about *what* may be
done (which status moves where, who cannot be locked, which report is still
open) live in the services.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import DbSession, require_role
from app.models import User
from app.schemas.admin import (
    AdminCourseOut,
    AdminCourseStatus,
    AdminPersonOut,
    AdminReportOut,
    AdminSummaryOut,
    AdminUserOut,
    CourseDecisionIn,
    HotCourseOut,
    PlatformOverviewOut,
    ReportCourseRef,
    ReportDismissIn,
    ReportResolveIn,
    ReportTargetOut,
)
from app.schemas.banners import (
    AdminBannerOut,
    BannerCreate,
    BannerOrderIn,
    BannerUpdate,
    BannerUploadIn,
    BannerUploadTicket,
)
from app.schemas.categories import (
    AdminCategoryOut,
    AdminCategoryTree,
    CategoryCreate,
    CategoryOrderIn,
    CategoryOut,
    CategoryUpdate,
)
from app.schemas.coupons import (
    AdminCouponCreate,
    AdminCouponOut,
    AdminCouponUpdate,
    CouponCourseRef,
)
from app.schemas.instructor_stats import StatsPeriod
from app.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.schemas.reports import ReportTargetType
from app.services import admin_coupons as coupons_service
from app.services import admin_users as users_service
from app.services import banners as banners_service
from app.services import categories as categories_service
from app.services import moderation as moderation_service
from app.services import platform_stats as stats_service
from app.services import reports as reports_service
from app.services.storage import ObjectStorage, get_storage
from app.services.tasks import TaskQueue, get_task_queue

router = APIRouter(prefix="/admin", tags=["admin"])

Admin = Annotated[User, Depends(require_role("admin"))]
#: Celery, and overridden in tests.
Queue = Annotated[TaskQueue, Depends(get_task_queue)]
Storage = Annotated[ObjectStorage, Depends(get_storage)]
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Search = Annotated[str | None, Query(max_length=100)]


@router.get("/summary", response_model=AdminSummaryOut)
async def get_summary(_: Admin, session: DbSession) -> AdminSummaryOut:
    """The numbers on the admin's tabs: what is waiting for a decision."""
    return AdminSummaryOut(
        pending_courses=await moderation_service.pending_count(session),
        pending_reports=await reports_service.pending_count(session),
        locked_users=await users_service.locked_count(session),
    )


# --- The platform dashboard -----------------------------------------------


@router.get("/stats/overview", response_model=PlatformOverviewOut)
async def get_platform_overview(
    _: Admin, session: DbSession, period: StatsPeriod = "30d"
) -> PlatformOverviewOut:
    """Revenue, orders, enrolments, sign-ups and active users for the period,
    bucket by bucket, against the period just before -- plus all-time totals."""
    return PlatformOverviewOut.model_validate(await stats_service.overview(session, period))


@router.get("/stats/hot-courses", response_model=Page[HotCourseOut])
async def list_hot_courses(
    _: Admin,
    session: DbSession,
    period: StatsPeriod = "30d",
    page: PageNo = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 10,
) -> Page[HotCourseOut]:
    """Courses with the most new enrolments in the period, then the most revenue."""
    items, total = await stats_service.hot_courses(
        session, period, page=page, page_size=page_size
    )
    return Page[HotCourseOut](
        items=[
            HotCourseOut(
                id=item.course.id,
                title=item.course.title,
                slug=item.course.slug,
                status=item.course.status,
                is_deleted=item.course.deleted_at is not None,
                thumbnail_url=item.course.thumbnail_url,
                price=item.course.price,
                rating_avg=item.course.rating_avg,
                students_count=item.course.students_count,
                instructor_name=item.instructor.full_name,
                new_enrollments=item.new_enrollments,
                sales=item.sales,
                revenue=item.revenue,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# --- Courses ---------------------------------------------------------------


def _course_out(item: moderation_service.AdminCourse) -> AdminCourseOut:
    course = item.course
    return AdminCourseOut(
        id=course.id,
        title=course.title,
        slug=course.slug,
        subtitle=course.subtitle,
        description=course.description,
        thumbnail_url=course.thumbnail_url,
        price=course.price,
        level=course.level,
        status=course.status,
        rejection_reason=course.rejection_reason,
        published_at=course.published_at,
        created_at=course.created_at,
        updated_at=course.updated_at,
        duration_total_s=course.duration_total_s,
        lessons_count=item.lessons_count,
        students_count=course.students_count,
        instructor=AdminPersonOut.model_validate(item.instructor),
        category=CategoryOut.model_validate(item.category),
    )


@router.get("/courses", response_model=Page[AdminCourseOut])
async def list_courses(
    _: Admin,
    session: DbSession,
    status: AdminCourseStatus = "pending_review",
    q: Search = None,
    page: PageNo = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[AdminCourseOut]:
    """The review queue by default -- longest waiting first. Search matches the
    title or the instructor's name or email."""
    items, total = await moderation_service.list_courses(
        session, status=status, q=q, page=page, page_size=page_size
    )
    return Page[AdminCourseOut](
        items=[_course_out(item) for item in items], total=total, page=page, page_size=page_size
    )


@router.get("/courses/{course_id}", response_model=AdminCourseOut)
async def get_course(course_id: uuid.UUID, _: Admin, session: DbSession) -> AdminCourseOut:
    """One course in any status. Its curriculum and lessons are read through the
    ordinary course endpoints, which already open everything to an admin."""
    return _course_out(await moderation_service.get_course(session, course_id))


@router.post("/courses/{course_id}/approve", response_model=AdminCourseOut)
async def approve_course(
    course_id: uuid.UUID, _: Admin, session: DbSession, queue: Queue
) -> AdminCourseOut:
    """pending_review -> published. Schedules the chatbot ingest and the course
    embedding, and tells the instructor."""
    return _course_out(await moderation_service.approve(session, course_id, queue))


@router.post("/courses/{course_id}/reject", response_model=AdminCourseOut)
async def reject_course(
    course_id: uuid.UUID, body: CourseDecisionIn, _: Admin, session: DbSession
) -> AdminCourseOut:
    """pending_review -> rejected, with the reason the instructor reads."""
    return _course_out(await moderation_service.reject(session, course_id, body.reason))


@router.post("/courses/{course_id}/take-down", response_model=AdminCourseOut)
async def take_down_course(
    course_id: uuid.UUID, body: CourseDecisionIn, _: Admin, session: DbSession
) -> AdminCourseOut:
    """published -> draft: off the platform, with the reason. Enrolments stay."""
    return _course_out(await moderation_service.take_down(session, course_id, body.reason))


# --- Categories ------------------------------------------------------------


async def _category_tree(session) -> list[AdminCategoryTree]:
    counts = await categories_service.course_counts(session)

    def out(category) -> AdminCategoryOut:
        return AdminCategoryOut(
            **CategoryOut.model_validate(category).model_dump(),
            parent_id=category.parent_id,
            courses_count=counts.get(category.id, 0),
        )

    return [
        AdminCategoryTree(**out(parent).model_dump(), children=[out(c) for c in children])
        for parent, children in await categories_service.list_tree(session)
    ]


@router.get("/categories", response_model=list[AdminCategoryTree])
async def list_categories(_: Admin, session: DbSession) -> list[AdminCategoryTree]:
    """The whole tree with how many courses each category holds. Unpaginated,
    like the public list: a curated taxonomy of a few dozen rows."""
    return await _category_tree(session)


@router.post(
    "/categories", response_model=AdminCategoryOut, status_code=status.HTTP_201_CREATED
)
async def create_category(
    body: CategoryCreate, _: Admin, session: DbSession
) -> AdminCategoryOut:
    """A top-level category, or one nested under a top-level one. Goes last."""
    category = await categories_service.create(session, name=body.name, parent_id=body.parent_id)
    return AdminCategoryOut(
        **CategoryOut.model_validate(category).model_dump(),
        parent_id=category.parent_id,
        courses_count=0,
    )


@router.patch("/categories/{category_id}", response_model=AdminCategoryOut)
async def update_category(
    category_id: uuid.UUID, body: CategoryUpdate, _: Admin, session: DbSession
) -> AdminCategoryOut:
    """Rename and/or move. The slug stays what it was."""
    # `parent_id: null` sent is "move to the top level"; not sent is "stay".
    sent_parent = "parent_id" in body.model_fields_set
    category = await categories_service.update(
        session,
        category_id,
        name=body.name,
        parent_id=body.parent_id if sent_parent else categories_service.UNSET,
    )
    counts = await categories_service.course_counts(session)
    return AdminCategoryOut(
        **CategoryOut.model_validate(category).model_dump(),
        parent_id=category.parent_id,
        courses_count=counts.get(category.id, 0),
    )


@router.put("/categories/order", response_model=list[AdminCategoryTree])
async def reorder_categories(
    body: CategoryOrderIn, _: Admin, session: DbSession
) -> list[AdminCategoryTree]:
    """The full order of one level. Answers with the whole tree."""
    await categories_service.reorder(session, body.parent_id, body.ids)
    return await _category_tree(session)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: uuid.UUID, _: Admin, session: DbSession) -> None:
    """Refused (409) while courses or child categories still use it."""
    await categories_service.delete(session, category_id)


# --- Coupons ---------------------------------------------------------------


def _coupon_out(item: coupons_service.AdminCoupon) -> AdminCouponOut:
    coupon = item.coupon
    return AdminCouponOut(
        id=coupon.id,
        code=coupon.code,
        discount_type=coupon.discount_type,
        value=coupon.value,
        scope=coupon.scope,
        courses=[CouponCourseRef(id=ref.id, title=ref.title) for ref in item.courses],
        max_uses=coupon.max_uses,
        used_count=coupon.used_count,
        valid_from=coupon.valid_from,
        valid_to=coupon.valid_to,
        status=item.status,
        created_at=coupon.created_at,
    )


@router.get("/coupons", response_model=Page[AdminCouponOut])
async def list_coupons(
    _: Admin,
    session: DbSession,
    status: coupons_service.CouponStatusFilter = "all",
    q: Search = None,
    page: PageNo = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[AdminCouponOut]:
    """Every campaign, newest first; `status` is derived from dates and uses."""
    items, total = await coupons_service.list_coupons(
        session, status_filter=status, q=q, page=page, page_size=page_size
    )
    return Page[AdminCouponOut](
        items=[_coupon_out(item) for item in items], total=total, page=page, page_size=page_size
    )


@router.post("/coupons", response_model=AdminCouponOut, status_code=status.HTTP_201_CREATED)
async def create_coupon(body: AdminCouponCreate, _: Admin, session: DbSession) -> AdminCouponOut:
    """A site-wide code, or one limited to the listed courses."""
    return _coupon_out(
        await coupons_service.create(
            session,
            code=body.code,
            discount_type=body.discount_type,
            value=body.value,
            scope=body.scope,
            course_ids=body.course_ids,
            max_uses=body.max_uses,
            valid_from=body.valid_from,
            valid_to=body.valid_to,
        )
    )


@router.patch("/coupons/{coupon_id}", response_model=AdminCouponOut)
async def update_coupon(
    coupon_id: uuid.UUID, body: AdminCouponUpdate, _: Admin, session: DbSession
) -> AdminCouponOut:
    """Change anything but the code. Orders already placed keep their numbers."""
    return _coupon_out(
        await coupons_service.update(session, coupon_id, body.model_dump(exclude_unset=True))
    )


@router.post("/coupons/{coupon_id}/end", response_model=AdminCouponOut)
async def end_coupon(coupon_id: uuid.UUID, _: Admin, session: DbSession) -> AdminCouponOut:
    """Stop accepting the code now (`valid_to = now`)."""
    return _coupon_out(await coupons_service.end_now(session, coupon_id))


@router.delete("/coupons/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coupon(coupon_id: uuid.UUID, _: Admin, session: DbSession) -> None:
    """Only a code nobody has used; a used one is ended instead (409)."""
    await coupons_service.delete_coupon(session, coupon_id)


# --- Homepage banners ------------------------------------------------------


def _banner_out(banner) -> AdminBannerOut:
    return AdminBannerOut(
        id=banner.id,
        title=banner.title,
        image_url=banner.image_url,
        link_url=banner.link_url,
        position=banner.position,
        is_active=banner.is_active,
        starts_at=banner.starts_at,
        ends_at=banner.ends_at,
        status=banners_service.status_of(banner, datetime.now(UTC)),
        created_at=banner.created_at,
    )


@router.get("/banners", response_model=list[AdminBannerOut])
async def list_banners(_: Admin, session: DbSession) -> list[AdminBannerOut]:
    """Every banner in the homepage's order, whether showing or not."""
    return [_banner_out(banner) for banner in await banners_service.list_all(session)]


@router.post("/banners/upload-url", response_model=BannerUploadTicket)
async def create_banner_upload(
    body: BannerUploadIn, _: Admin, storage: Storage
) -> BannerUploadTicket:
    """Sign a PUT for one new picture. Nothing is written until the banner is."""
    url, key, ttl = banners_service.upload_ticket(
        storage,
        filename=body.filename,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
    )
    return BannerUploadTicket(
        upload_url=url, storage_key=key, expires_in=ttl, content_type=body.content_type
    )


@router.post("/banners", response_model=AdminBannerOut, status_code=status.HTTP_201_CREATED)
async def create_banner(
    body: BannerCreate, _: Admin, session: DbSession, storage: Storage
) -> AdminBannerOut:
    """A new banner, last in line, with a picture uploaded through the ticket."""
    banner = await banners_service.create(
        session,
        storage,
        title=body.title,
        image_key=body.image_key,
        link_url=body.link_url,
        is_active=body.is_active,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
    )
    return _banner_out(banner)


@router.put("/banners/order", response_model=list[AdminBannerOut])
async def reorder_banners(
    body: BannerOrderIn, _: Admin, session: DbSession
) -> list[AdminBannerOut]:
    """The whole order at once."""
    return [_banner_out(b) for b in await banners_service.reorder(session, body.ids)]


@router.patch("/banners/{banner_id}", response_model=AdminBannerOut)
async def update_banner(
    banner_id: uuid.UUID, body: BannerUpdate, _: Admin, session: DbSession, storage: Storage
) -> AdminBannerOut:
    """Change what was sent; a new `image_key` replaces the picture."""
    banner = await banners_service.update(
        session, storage, banner_id, body.model_dump(exclude_unset=True)
    )
    return _banner_out(banner)


@router.delete("/banners/{banner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_banner(
    banner_id: uuid.UUID, _: Admin, session: DbSession, storage: Storage
) -> None:
    await banners_service.delete(session, storage, banner_id)


# --- Users -----------------------------------------------------------------


def _user_out(item: users_service.AdminUser) -> AdminUserOut:
    user = item.user
    return AdminUserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        avatar_url=user.avatar_url,
        role=user.role,
        locked_at=user.locked_at,
        oauth_provider=user.oauth_provider,
        has_password=user.has_password,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        courses_count=item.courses_count,
        enrollments_count=item.enrollments_count,
    )


@router.get("/users", response_model=Page[AdminUserOut])
async def list_users(
    _: Admin,
    session: DbSession,
    q: Search = None,
    role: users_service.RoleFilter = "all",
    lock: users_service.LockFilter = "all",
    page: PageNo = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[AdminUserOut]:
    """Every account, newest first. `lock=locked` lists the locked ones."""
    items, total = await users_service.list_users(
        session, q=q, role=role, lock=lock, page=page, page_size=page_size
    )
    return Page[AdminUserOut](
        items=[_user_out(item) for item in items], total=total, page=page, page_size=page_size
    )


@router.post("/users/{user_id}/lock", response_model=AdminUserOut)
async def lock_user(user_id: uuid.UUID, _: Admin, session: DbSession) -> AdminUserOut:
    """Block sign-in and end every session now. Admin accounts cannot be locked."""
    return _user_out(await users_service.lock(session, user_id))


@router.post("/users/{user_id}/unlock", response_model=AdminUserOut)
async def unlock_user(user_id: uuid.UUID, _: Admin, session: DbSession) -> AdminUserOut:
    return _user_out(await users_service.unlock(session, user_id))


# --- Reports ---------------------------------------------------------------


def _report_out(item: reports_service.AdminReport) -> AdminReportOut:
    report, target = item.report, item.target
    return AdminReportOut(
        id=report.id,
        target_type=report.target_type,
        target_id=report.target_id,
        reason=report.reason,
        details=report.details,
        status=report.status,
        created_at=report.created_at,
        reporter=AdminPersonOut.model_validate(item.reporter),
        target=ReportTargetOut(
            exists=target.exists,
            title=target.title,
            excerpt=target.excerpt,
            rating=target.rating,
            author=AdminPersonOut.model_validate(target.author) if target.author else None,
            course=ReportCourseRef.model_validate(target.course) if target.course else None,
            lesson_id=target.lesson_id,
            thread_id=target.thread_id,
        ),
        pending_on_target=item.pending_on_target,
        resolved_at=report.resolved_at,
        resolved_by=AdminPersonOut.model_validate(item.resolver) if item.resolver else None,
        resolution_note=report.resolution_note,
        content_removed=report.content_removed,
    )


@router.get("/reports", response_model=Page[AdminReportOut])
async def list_reports(
    _: Admin,
    session: DbSession,
    status: reports_service.ReportStatusFilter = "pending",
    target_type: ReportTargetType | None = None,
    page: PageNo = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[AdminReportOut]:
    """Pending reports oldest first, or closed ones newest decision first --
    each with the reported content as it is now."""
    items, total = await reports_service.list_for_admin(
        session, status_filter=status, target_type=target_type, page=page, page_size=page_size
    )
    return Page[AdminReportOut](
        items=[_report_out(item) for item in items], total=total, page=page, page_size=page_size
    )


@router.post("/reports/{report_id}/review", response_model=AdminReportOut)
async def start_review(report_id: uuid.UUID, _: Admin, session: DbSession) -> AdminReportOut:
    """open -> reviewing: mark that somebody is looking at it."""
    return _report_out(await reports_service.start_review(session, report_id))


@router.post("/reports/{report_id}/resolve", response_model=AdminReportOut)
async def resolve_report(
    report_id: uuid.UUID, body: ReportResolveIn, admin: Admin, session: DbSession
) -> AdminReportOut:
    """The report was right. `remove_content` also takes the content down.
    Closes every pending report on the same content."""
    return _report_out(
        await reports_service.resolve(
            session, report_id, admin, note=body.note, remove_content=body.remove_content
        )
    )


@router.post("/reports/{report_id}/dismiss", response_model=AdminReportOut)
async def dismiss_report(
    report_id: uuid.UUID, body: ReportDismissIn, admin: Admin, session: DbSession
) -> AdminReportOut:
    """The content stays. Closes every pending report on it."""
    return _report_out(await reports_service.dismiss(session, report_id, admin, note=body.note))
