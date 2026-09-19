"""Metadata tests for the first three tables.

These run without a database: they check that the models say what
docs/database-design.md says. The migration itself is verified by running
upgrade/downgrade against the dev database.
"""

import pytest

from app.models import (
    EMBEDDING_DIMENSIONS,
    Base,
    Bookmark,
    Category,
    Course,
    CourseSection,
    DocChunk,
    Enrollment,
    Lesson,
    LessonProgress,
    Note,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    RefreshToken,
    Review,
    User,
    VideoAsset,
)


def constraint_names(model: type) -> set[str]:
    return {c.name for c in model.__table__.constraints if c.name}


def index_names(model: type) -> set[str]:
    return {i.name for i in model.__table__.indexes}


def test_registered_tables_match_the_phases_done_so_far() -> None:
    """Phase 1 created three; every table after that arrives with the feature
    that reads it -- Phase 2's curriculum and enrolments, then Phase 3's four
    grading tables."""
    assert set(Base.metadata.tables) == {
        "users",
        "categories",
        "courses",
        "refresh_tokens",
        "course_sections",
        "lessons",
        "video_assets",
        "enrollments",
        "lesson_progress",
        "notes",
        "bookmarks",
        "reviews",
        # Phase 3 -- code grading.
        "code_exercises",
        "test_cases",
        "submissions",
        "submission_results",
        # Phase 4 -- what the RAG assistant retrieves from.
        "doc_chunks",
        # Phase 4 -- quizzes.
        "quizzes",
        "quiz_questions",
        "quiz_attempts",
        # Phase 4 -- conversations with the RAG assistant.
        "chat_sessions",
        "chat_messages",
    }


@pytest.mark.parametrize("model", [User, Category, Course])
def test_every_table_has_uuid_pk_and_timestamps(model: type) -> None:
    table = model.__table__
    assert [c.name for c in table.primary_key.columns] == ["id"]
    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False


def test_users_constraints_match_the_spec() -> None:
    assert {"ck_users_role", "ck_users_credential"} <= constraint_names(User)
    assert {"uq_users_email", "uq_users_oauth", "ix_users_role"} == index_names(User)


def test_users_oauth_index_is_partial() -> None:
    """A unique index over two nullable columns would not constrain much."""
    index = next(i for i in User.__table__.indexes if i.name == "uq_users_oauth")
    assert index.unique is True
    assert "oauth_sub IS NOT NULL" in str(index.dialect_options["postgresql"]["where"])


def test_password_hash_is_optional_but_full_name_is_not() -> None:
    assert User.__table__.c.password_hash.nullable is True
    assert User.__table__.c.full_name.nullable is False


def test_categories_constraints_match_the_spec() -> None:
    assert "ck_categories_not_self_parent" in constraint_names(Category)
    assert {"uq_categories_slug", "ix_categories_parent_id"} == index_names(Category)


def test_category_parent_is_self_referential_and_restricted() -> None:
    fk = next(iter(Category.__table__.c.parent_id.foreign_keys))
    assert fk.column.table.name == "categories"
    assert fk.ondelete == "RESTRICT"


def test_courses_check_constraints_match_the_spec() -> None:
    expected = {
        "ck_courses_status",
        "ck_courses_level",
        "ck_courses_price_non_negative",
        "ck_courses_rating_range",
        "ck_courses_published_at",
        "ck_courses_rejection_reason",
    }
    assert expected <= constraint_names(Course)


def test_courses_indexes_match_the_spec() -> None:
    expected = {
        "uq_courses_slug",
        "ix_courses_listing",
        "ix_courses_rating",
        "ix_courses_search_vector",
        "ix_courses_category_id",
        "ix_courses_instructor_id",
    }
    assert expected == index_names(Course)


def test_listing_indexes_exclude_soft_deleted_rows() -> None:
    """Public queries always filter deleted_at IS NULL; the index must agree."""
    for name in ("ix_courses_listing", "ix_courses_rating"):
        index = next(i for i in Course.__table__.indexes if i.name == name)
        where = str(index.dialect_options["postgresql"]["where"])
        assert "deleted_at IS NULL" in where


def test_search_vector_index_is_gin() -> None:
    index = next(
        i for i in Course.__table__.indexes if i.name == "ix_courses_search_vector"
    )
    assert index.dialect_options["postgresql"]["using"] == "gin"


def test_money_and_rating_are_numeric_not_float() -> None:
    """Float money is a bug that shows up months later, in someone's invoice."""
    assert Course.__table__.c.price.type.python_type is __import__("decimal").Decimal
    assert Course.__table__.c.price.type.scale == 2
    assert Course.__table__.c.rating_avg.type.scale == 2


def test_course_owner_references_cannot_orphan_rows() -> None:
    for column in ("instructor_id", "category_id"):
        fk = next(iter(Course.__table__.c[column].foreign_keys))
        assert fk.ondelete == "RESTRICT"


def test_courses_is_the_only_soft_deleted_table() -> None:
    assert "deleted_at" in Course.__table__.c
    assert "deleted_at" not in User.__table__.c
    assert "deleted_at" not in Category.__table__.c


def test_refresh_tokens_indexes_match_the_spec() -> None:
    assert {"uq_refresh_tokens_token_hash", "ix_refresh_tokens_user_id"} == index_names(
        RefreshToken
    )


def test_refresh_token_hash_column_fits_sha256_hex() -> None:
    """Only the hash is stored: a leaked database must not yield usable tokens."""
    assert RefreshToken.__table__.c.token_hash.type.length == 64
    assert "token" not in {
        c.name for c in RefreshToken.__table__.columns if c.name != "token_hash"
    }


def test_deleting_a_user_takes_their_sessions_with_them() -> None:
    fk = next(iter(RefreshToken.__table__.c.user_id.foreign_keys))
    assert fk.column.table.name == "users"
    assert fk.ondelete == "CASCADE"


def test_refresh_token_records_expiry_and_revocation() -> None:
    table = RefreshToken.__table__
    assert table.c.expires_at.nullable is False
    assert table.c.revoked_at.nullable is True


def test_refresh_token_has_created_at_but_no_updated_at() -> None:
    """Deviates from the project-wide timestamp pair on purpose.

    docs/database-design.md gives this table `created_at` only: a session row
    is written once and then at most revoked, and `revoked_at` says when that
    happened more precisely than a generic `updated_at` would.
    """
    assert "created_at" in RefreshToken.__table__.c
    assert "updated_at" not in RefreshToken.__table__.c


def test_positions_are_unique_per_parent_and_deferrable() -> None:
    """Reordering rewrites several rows in one transaction.

    With an immediate constraint the second UPDATE collides with the first,
    before the arrangement the instructor asked for even exists.
    """
    for model, name in (
        (CourseSection, "uq_course_sections_position"),
        (Lesson, "uq_lessons_position"),
    ):
        constraint = next(
            c for c in model.__table__.constraints if c.name == name
        )
        assert constraint.deferrable is True
        assert constraint.initially == "DEFERRED"


def test_deleting_a_course_takes_its_curriculum_with_it() -> None:
    section_fk = next(iter(CourseSection.__table__.c.course_id.foreign_keys))
    lesson_fk = next(iter(Lesson.__table__.c.section_id.foreign_keys))

    assert section_fk.ondelete == "CASCADE"
    assert lesson_fk.ondelete == "CASCADE"


def test_losing_a_video_does_not_delete_the_lesson() -> None:
    """SET NULL: the lesson stays, its slot in the order stays, the video is gone."""
    fk = next(iter(Lesson.__table__.c.video_asset_id.foreign_keys))

    assert fk.ondelete == "SET NULL"


def test_only_video_lessons_may_carry_a_video() -> None:
    names = {c.name for c in Lesson.__table__.constraints if c.name}

    assert {"ck_lessons_type", "ck_lessons_video_asset_type"} <= names


def test_video_assets_are_keyed_by_their_storage_object() -> None:
    names = {c.name for c in VideoAsset.__table__.constraints if c.name}

    assert "uq_video_assets_storage_key" in names
    assert "ck_video_assets_status" in names


def test_enrollments_constraints_match_the_spec() -> None:
    assert "ck_enrollments_source" in constraint_names(Enrollment)
    assert "uq_enrollments_user_course" in constraint_names(Enrollment)
    assert {"ix_enrollments_user_id"} == index_names(Enrollment)


def test_an_enrolment_outlives_its_course_but_not_its_owner() -> None:
    """A course is only soft-deleted, so nothing may cascade from it."""
    user_fk = next(iter(Enrollment.__table__.c.user_id.foreign_keys))
    course_fk = next(iter(Enrollment.__table__.c.course_id.foreign_keys))

    assert user_fk.ondelete == "CASCADE"
    assert course_fk.ondelete == "RESTRICT"


def test_lesson_progress_constraints_match_the_spec() -> None:
    assert "uq_lesson_progress_enrollment_lesson" in constraint_names(LessonProgress)
    assert "ck_lesson_progress_position_non_negative" in constraint_names(LessonProgress)


def test_lesson_progress_needs_no_index_of_its_own() -> None:
    """The unique constraint already leads with `enrollment_id`.

    docs/database-design.md used to list `ix_lesson_progress_enrollment` as
    well; a second B-tree on the leading column of an existing one would be
    paid for on every heartbeat and read by nothing.
    """
    assert index_names(LessonProgress) == set()


def test_progress_dies_with_whatever_it_describes() -> None:
    for column in ("enrollment_id", "lesson_id"):
        fk = next(iter(LessonProgress.__table__.c[column].foreign_keys))
        assert fk.ondelete == "CASCADE"


def test_notes_and_bookmarks_belong_to_the_person_not_the_enrolment() -> None:
    """Progress describes one run at a course; a note is the reader's own work."""
    for model in (Note, Bookmark):
        columns = set(model.__table__.c.keys())
        assert "user_id" in columns
        assert "enrollment_id" not in columns
        for column in ("user_id", "lesson_id"):
            fk = next(iter(model.__table__.c[column].foreign_keys))
            assert fk.ondelete == "CASCADE"


def test_a_lesson_holds_many_notes_but_one_bookmark() -> None:
    assert "uq_bookmarks_user_lesson" in constraint_names(Bookmark)
    assert {"ix_notes_user_lesson"} == index_names(Note)
    assert all(not index.unique for index in Note.__table__.indexes)


def test_a_note_cannot_be_empty_or_before_the_video_starts() -> None:
    assert {
        "ck_notes_content_not_empty",
        "ck_notes_timestamp_non_negative",
    } <= constraint_names(Note)


def test_a_review_belongs_to_one_person_and_one_course() -> None:
    """Unlike an enrolment, a review dies with the course: it is *about* it."""
    for column in ("course_id", "user_id"):
        fk = next(iter(Review.__table__.c[column].foreign_keys))
        assert fk.ondelete == "CASCADE"

    assert "uq_reviews_course_user" in constraint_names(Review)


def test_a_review_is_one_to_five_stars_and_never_a_blank_comment() -> None:
    assert {
        "ck_reviews_rating",
        "ck_reviews_comment_not_blank",
    } <= constraint_names(Review)


def test_a_chunk_is_always_attached_to_a_citable_lesson() -> None:
    """Both parents cascade, and neither is optional.

    A chunk whose lesson has been deleted would be the assistant quoting
    material the course no longer contains; a chunk with no lesson at all would
    be an answer with no source to link to.
    """
    for column in ("course_id", "lesson_id"):
        assert DocChunk.__table__.c[column].nullable is False
        fk = next(iter(DocChunk.__table__.c[column].foreign_keys))
        assert fk.ondelete == "CASCADE"


def test_chunk_embeddings_are_fixed_width() -> None:
    """The width lives in the column type, so a model change cannot be quiet."""
    assert DocChunk.__table__.c.embedding.type.dim == EMBEDDING_DIMENSIONS
    assert EMBEDDING_DIMENSIONS <= 2000, "over pgvector's HNSW ceiling for `vector`"
    assert DocChunk.__table__.c.embedding_model.nullable is False


def test_the_embedding_index_is_hnsw_over_cosine_distance() -> None:
    """The operator class has to match the operator the retrieval query uses.

    Build it with the wrong one and nothing fails: the planner just ignores the
    index and every question becomes a sequential scan of the whole corpus.
    """
    index = next(i for i in DocChunk.__table__.indexes if i.name == "ix_doc_chunks_embedding")
    assert index.dialect_options["postgresql"]["using"] == "hnsw"
    assert index.dialect_options["postgresql"]["ops"] == {"embedding": "vector_cosine_ops"}
    assert index_names(DocChunk) == {"ix_doc_chunks_course_id", "ix_doc_chunks_embedding"}


def test_re_ingesting_a_lesson_cannot_double_its_chunks() -> None:
    assert "uq_doc_chunks_lesson_chunk" in constraint_names(DocChunk)
    assert {
        "ck_doc_chunks_chunk_index",
        "ck_doc_chunks_content_not_empty",
        "ck_doc_chunks_token_count",
    } <= constraint_names(DocChunk)


def test_a_lesson_has_at_most_one_quiz() -> None:
    """Two quizzes behind one lesson would make "the quiz" ambiguous."""
    assert "uq_quizzes_lesson" in constraint_names(Quiz)
    assert Quiz.__table__.c.lesson_id.nullable is False
    fk = next(iter(Quiz.__table__.c.lesson_id.foreign_keys))
    assert fk.ondelete == "CASCADE"


def test_a_question_cannot_point_past_its_own_options() -> None:
    """The rule that keeps a question answerable, in the table.

    docs/database-design.md left this to the service. It is written into the
    constraint instead, because the service is not the only writer: the quiz
    generator of the next task inserts straight from a model's JSON output.
    """
    assert "ck_quiz_questions_options" in constraint_names(QuizQuestion)
    check = next(
        c for c in QuizQuestion.__table__.constraints if c.name == "ck_quiz_questions_options"
    )
    condition = str(check.sqltext)
    assert "correct_index < jsonb_array_length(options)" in condition
    # CASE, not AND: jsonb_array_length raises on a non-array rather than
    # returning false, and only CASE promises the order of evaluation.
    assert condition.strip().startswith("CASE")


def test_only_a_drafted_question_can_carry_a_review() -> None:
    """`reviewed_at` means "an AI draft, signed off". On a question the
    instructor typed it would count as an accepted draft that never was."""
    assert "ck_quiz_questions_review_ai_only" in constraint_names(QuizQuestion)
    assert QuizQuestion.__table__.c.ai_generated.nullable is False
    assert QuizQuestion.__table__.c.reviewed_at.nullable is True


def test_only_one_attempt_at_a_time_and_only_while_unfinished() -> None:
    """The index that makes a time limit mean anything.

    Without it, four tabs are four clocks and the student keeps the best one.
    Partial, so finished attempts pile up freely -- history is why they are
    kept at all.
    """
    index = next(i for i in QuizAttempt.__table__.indexes if i.name == "uq_quiz_attempts_open")
    assert index.unique is True
    assert "submitted_at IS NULL" in str(index.dialect_options["postgresql"]["where"])


def test_an_attempt_is_either_running_or_finished() -> None:
    """A score with no submission time is a half-applied write, not a state."""
    assert {
        "ck_quiz_attempts_finished",
        "ck_quiz_attempts_score",
        "ck_quiz_attempts_expired_scores_zero",
    } <= constraint_names(QuizAttempt)


def test_the_attempt_keeps_the_clock_it_started_under() -> None:
    """Editing the quiz must not move the deadline of someone sitting it."""
    assert QuizAttempt.__table__.c.time_limit_s is not None
    assert QuizAttempt.__table__.c.started_at.nullable is False
    assert QuizAttempt.__table__.c.submitted_at.nullable is True
