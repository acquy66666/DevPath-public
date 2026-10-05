--
-- PostgreSQL database dump
--


-- Dumped from database version 16.15 (Debian 16.15-1.pgdg12+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg12+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: unaccent; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;


--
-- Name: EXTENSION unaccent; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION unaccent IS 'text search dictionary that removes accents';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: courses_search_vector_refresh(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.courses_search_vector_refresh() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.search_vector := 
    setweight(to_tsvector('simple', unaccent(coalesce(NEW.title, ''))), 'A')
 || setweight(to_tsvector('simple', unaccent(coalesce(NEW.subtitle, ''))), 'B')
 || setweight(to_tsvector('simple', unaccent(coalesce(NEW.description, ''))), 'C')
;
            RETURN NEW;
        END;
        $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: banners; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.banners (
    title character varying(120) NOT NULL,
    image_url text NOT NULL,
    link_url text,
    "position" integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    starts_at timestamp with time zone,
    ends_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_banners_period CHECK (((starts_at IS NULL) OR (ends_at IS NULL) OR (ends_at > starts_at))),
    CONSTRAINT ck_banners_title_not_empty CHECK ((length((title)::text) > 0))
);


--
-- Name: bookmarks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bookmarks (
    user_id uuid NOT NULL,
    lesson_id uuid NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: cart_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cart_items (
    cart_id uuid NOT NULL,
    course_id uuid NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: carts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.carts (
    user_id uuid NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    name character varying(100) NOT NULL,
    slug character varying(120) NOT NULL,
    parent_id uuid,
    "position" integer DEFAULT 0 NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_categories_not_self_parent CHECK ((parent_id IS DISTINCT FROM id))
);


--
-- Name: certificates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.certificates (
    enrollment_id uuid NOT NULL,
    code character varying(16) NOT NULL,
    recipient_name character varying(150) NOT NULL,
    course_title character varying(200) NOT NULL,
    instructor_name character varying(150) NOT NULL,
    issued_at timestamp with time zone NOT NULL,
    pdf_key text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_certificates_code_format CHECK (((code)::text ~ '^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{16}$'::text))
);


--
-- Name: chat_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_messages (
    session_id uuid NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    cited_lesson_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_chat_messages_cited_is_array CHECK ((jsonb_typeof(cited_lesson_ids) = 'array'::text)),
    CONSTRAINT ck_chat_messages_content_not_empty CHECK ((length(content) > 0)),
    CONSTRAINT ck_chat_messages_role CHECK (((role)::text = ANY (ARRAY[('user'::character varying)::text, ('assistant'::character varying)::text])))
);


--
-- Name: chat_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_sessions (
    user_id uuid NOT NULL,
    course_id uuid NOT NULL,
    title character varying(120),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: code_exercises; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.code_exercises (
    lesson_id uuid NOT NULL,
    statement_md text NOT NULL,
    language character varying(20) DEFAULT 'python'::character varying NOT NULL,
    starter_code text,
    time_limit_ms integer DEFAULT 2000 NOT NULL,
    memory_limit_mb integer DEFAULT 256 NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_code_exercises_language CHECK (((language)::text = 'python'::text)),
    CONSTRAINT ck_code_exercises_memory_limit CHECK (((memory_limit_mb >= 16) AND (memory_limit_mb <= 512))),
    CONSTRAINT ck_code_exercises_time_limit CHECK (((time_limit_ms >= 100) AND (time_limit_ms <= 10000)))
);


--
-- Name: coupon_courses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.coupon_courses (
    coupon_id uuid NOT NULL,
    course_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: coupons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.coupons (
    code character varying(32) NOT NULL,
    discount_type character varying(10) NOT NULL,
    value numeric(12,2) NOT NULL,
    scope character varying(10) DEFAULT 'site'::character varying NOT NULL,
    max_uses integer,
    used_count integer DEFAULT 0 NOT NULL,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_coupons_code_length CHECK ((length((code)::text) >= 3)),
    CONSTRAINT ck_coupons_code_upper CHECK (((code)::text = upper((code)::text))),
    CONSTRAINT ck_coupons_discount_type CHECK (((discount_type)::text = ANY (ARRAY[('percent'::character varying)::text, ('fixed'::character varying)::text]))),
    CONSTRAINT ck_coupons_max_uses CHECK (((max_uses IS NULL) OR (max_uses > 0))),
    CONSTRAINT ck_coupons_percent_range CHECK ((((discount_type)::text <> 'percent'::text) OR (value <= (100)::numeric))),
    CONSTRAINT ck_coupons_period CHECK (((valid_to IS NULL) OR (valid_to > valid_from))),
    CONSTRAINT ck_coupons_scope CHECK (((scope)::text = ANY (ARRAY[('site'::character varying)::text, ('courses'::character varying)::text]))),
    CONSTRAINT ck_coupons_used_count CHECK ((used_count >= 0)),
    CONSTRAINT ck_coupons_uses_left CHECK (((max_uses IS NULL) OR (used_count <= max_uses))),
    CONSTRAINT ck_coupons_value_positive CHECK ((value > (0)::numeric))
);


--
-- Name: course_embeddings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.course_embeddings (
    course_id uuid NOT NULL,
    source_text text NOT NULL,
    embedding public.vector(768) NOT NULL,
    embedding_model character varying(60) NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_course_embeddings_source_not_empty CHECK ((length(source_text) > 0))
);


--
-- Name: course_sections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.course_sections (
    course_id uuid NOT NULL,
    title character varying(200) NOT NULL,
    "position" integer NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: courses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.courses (
    instructor_id uuid NOT NULL,
    category_id uuid NOT NULL,
    title character varying(200) NOT NULL,
    slug character varying(220) NOT NULL,
    subtitle character varying(300),
    description text,
    thumbnail_url text,
    price numeric(12,2) DEFAULT 0 NOT NULL,
    level character varying(20) DEFAULT 'beginner'::character varying NOT NULL,
    language character varying(10) DEFAULT 'vi'::character varying NOT NULL,
    status character varying(20) DEFAULT 'draft'::character varying NOT NULL,
    rejection_reason text,
    published_at timestamp with time zone,
    rating_avg numeric(3,2) DEFAULT 0 NOT NULL,
    rating_count integer DEFAULT 0 NOT NULL,
    students_count integer DEFAULT 0 NOT NULL,
    duration_total_s integer DEFAULT 0 NOT NULL,
    search_vector tsvector,
    deleted_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_courses_level CHECK (((level)::text = ANY (ARRAY[('beginner'::character varying)::text, ('intermediate'::character varying)::text, ('advanced'::character varying)::text]))),
    CONSTRAINT ck_courses_price_non_negative CHECK ((price >= (0)::numeric)),
    CONSTRAINT ck_courses_published_at CHECK ((((status)::text <> 'published'::text) OR (published_at IS NOT NULL))),
    CONSTRAINT ck_courses_rating_range CHECK (((rating_avg >= (0)::numeric) AND (rating_avg <= (5)::numeric) AND (rating_count >= 0))),
    CONSTRAINT ck_courses_rejection_reason CHECK ((((status)::text <> 'rejected'::text) OR (rejection_reason IS NOT NULL))),
    CONSTRAINT ck_courses_status CHECK (((status)::text = ANY (ARRAY[('draft'::character varying)::text, ('pending_review'::character varying)::text, ('published'::character varying)::text, ('rejected'::character varying)::text])))
);


--
-- Name: doc_chunks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.doc_chunks (
    course_id uuid NOT NULL,
    lesson_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    token_count integer NOT NULL,
    embedding public.vector(768) NOT NULL,
    embedding_model character varying(60) NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_doc_chunks_chunk_index CHECK ((chunk_index >= 0)),
    CONSTRAINT ck_doc_chunks_content_not_empty CHECK ((length(content) > 0)),
    CONSTRAINT ck_doc_chunks_token_count CHECK ((token_count > 0))
);


--
-- Name: enrollments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.enrollments (
    user_id uuid NOT NULL,
    course_id uuid NOT NULL,
    source character varying(20) DEFAULT 'free'::character varying NOT NULL,
    completed_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_enrollments_source CHECK (((source)::text = ANY (ARRAY[('free'::character varying)::text, ('purchase'::character varying)::text])))
);


--
-- Name: lesson_progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lesson_progress (
    enrollment_id uuid NOT NULL,
    lesson_id uuid NOT NULL,
    last_position_s integer DEFAULT 0 NOT NULL,
    completed_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_lesson_progress_position_non_negative CHECK ((last_position_s >= 0))
);


--
-- Name: lessons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lessons (
    section_id uuid NOT NULL,
    title character varying(200) NOT NULL,
    type character varying(20) NOT NULL,
    "position" integer NOT NULL,
    is_preview boolean DEFAULT false NOT NULL,
    video_asset_id uuid,
    article_content text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_lessons_type CHECK (((type)::text = ANY (ARRAY[('video'::character varying)::text, ('article'::character varying)::text, ('quiz'::character varying)::text, ('code_exercise'::character varying)::text]))),
    CONSTRAINT ck_lessons_video_asset_type CHECK (((video_asset_id IS NULL) OR ((type)::text = 'video'::text)))
);


--
-- Name: notes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notes (
    user_id uuid NOT NULL,
    lesson_id uuid NOT NULL,
    timestamp_s integer DEFAULT 0 NOT NULL,
    content text NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_notes_content_not_empty CHECK ((length(content) > 0)),
    CONSTRAINT ck_notes_timestamp_non_negative CHECK ((timestamp_s >= 0))
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    user_id uuid NOT NULL,
    type character varying(40) NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    read_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_notifications_payload_object CHECK ((jsonb_typeof(payload) = 'object'::text)),
    CONSTRAINT ck_notifications_type CHECK (((type)::text = ANY (ARRAY[('qa_reply'::character varying)::text, ('qa_question'::character varying)::text, ('course_approved'::character varying)::text, ('course_rejected'::character varying)::text, ('course_taken_down'::character varying)::text])))
);


--
-- Name: order_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.order_items (
    order_id uuid NOT NULL,
    course_id uuid NOT NULL,
    unit_price numeric(12,2) NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    discount numeric(12,2) DEFAULT 0 NOT NULL,
    CONSTRAINT ck_order_items_discount CHECK (((discount >= (0)::numeric) AND (discount <= unit_price))),
    CONSTRAINT ck_order_items_unit_price CHECK ((unit_price >= (0)::numeric))
);


--
-- Name: orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orders (
    user_id uuid NOT NULL,
    code character varying(14) NOT NULL,
    subtotal numeric(12,2) NOT NULL,
    discount numeric(12,2) DEFAULT 0 NOT NULL,
    total numeric(12,2) NOT NULL,
    coupon_id uuid,
    coupon_code character varying(32),
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    payment_provider character varying(20) DEFAULT 'vnpay'::character varying NOT NULL,
    provider_txn_id character varying(64),
    paid_at timestamp with time zone,
    failure_code character varying(10),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_orders_amounts_non_negative CHECK (((subtotal >= (0)::numeric) AND (discount >= (0)::numeric) AND (total >= (0)::numeric))),
    CONSTRAINT ck_orders_paid_evidence CHECK ((((status)::text = 'paid'::text) = ((paid_at IS NOT NULL) AND (provider_txn_id IS NOT NULL)))),
    CONSTRAINT ck_orders_provider CHECK (((payment_provider)::text = ANY (ARRAY[('vnpay'::character varying)::text, ('momo'::character varying)::text]))),
    CONSTRAINT ck_orders_status CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('paid'::character varying)::text, ('failed'::character varying)::text, ('cancelled'::character varying)::text]))),
    CONSTRAINT ck_orders_total CHECK ((total = (subtotal - discount)))
);


--
-- Name: orphan_objects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orphan_objects (
    key character varying(1024) NOT NULL,
    size_bytes bigint NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_events (
    order_id uuid,
    provider character varying(20) NOT NULL,
    payload jsonb NOT NULL,
    signature_valid boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    CONSTRAINT ck_payment_events_provider CHECK (((provider)::text = ANY (ARRAY[('vnpay'::character varying)::text, ('momo'::character varying)::text])))
);


--
-- Name: qa_replies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qa_replies (
    thread_id uuid NOT NULL,
    user_id uuid NOT NULL,
    body text NOT NULL,
    is_instructor_reply boolean DEFAULT false NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_qa_replies_body_not_empty CHECK ((length(body) > 0))
);


--
-- Name: qa_threads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qa_threads (
    lesson_id uuid NOT NULL,
    user_id uuid NOT NULL,
    title character varying(200) NOT NULL,
    body text NOT NULL,
    resolved_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_qa_threads_body_not_empty CHECK ((length(body) > 0)),
    CONSTRAINT ck_qa_threads_title_not_empty CHECK ((length((title)::text) > 0))
);


--
-- Name: qa_votes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qa_votes (
    thread_id uuid NOT NULL,
    user_id uuid NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: quiz_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quiz_attempts (
    quiz_id uuid NOT NULL,
    user_id uuid NOT NULL,
    answers jsonb,
    score integer,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    submitted_at timestamp with time zone,
    time_limit_s integer,
    expired boolean DEFAULT false NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_quiz_attempts_expired_scores_zero CHECK (((expired = false) OR ((submitted_at IS NOT NULL) AND (score = 0)))),
    CONSTRAINT ck_quiz_attempts_finished CHECK ((((submitted_at IS NULL) AND (score IS NULL) AND (answers IS NULL)) OR ((submitted_at IS NOT NULL) AND (score IS NOT NULL) AND (answers IS NOT NULL)))),
    CONSTRAINT ck_quiz_attempts_score CHECK (((score IS NULL) OR ((score >= 0) AND (score <= 100)))),
    CONSTRAINT ck_quiz_attempts_time_limit CHECK (((time_limit_s IS NULL) OR ((time_limit_s >= 30) AND (time_limit_s <= 7200))))
);


--
-- Name: quiz_questions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quiz_questions (
    quiz_id uuid NOT NULL,
    question text NOT NULL,
    options jsonb NOT NULL,
    correct_index integer NOT NULL,
    explanation text,
    "position" integer NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    ai_generated boolean DEFAULT false NOT NULL,
    reviewed_at timestamp with time zone,
    CONSTRAINT ck_quiz_questions_not_empty CHECK ((length(question) > 0)),
    CONSTRAINT ck_quiz_questions_options CHECK (
CASE
    WHEN (jsonb_typeof(options) = 'array'::text) THEN ((jsonb_array_length(options) >= 2) AND (jsonb_array_length(options) <= 6) AND (correct_index >= 0) AND (correct_index < jsonb_array_length(options)))
    ELSE false
END),
    CONSTRAINT ck_quiz_questions_review_ai_only CHECK ((ai_generated OR (reviewed_at IS NULL)))
);


--
-- Name: quizzes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quizzes (
    lesson_id uuid NOT NULL,
    time_limit_s integer,
    pass_score integer DEFAULT 70 NOT NULL,
    ai_generated boolean DEFAULT false NOT NULL,
    is_published boolean DEFAULT false NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_quizzes_pass_score CHECK (((pass_score >= 0) AND (pass_score <= 100))),
    CONSTRAINT ck_quizzes_time_limit CHECK (((time_limit_s IS NULL) OR ((time_limit_s >= 30) AND (time_limit_s <= 7200))))
);


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refresh_tokens (
    user_id uuid NOT NULL,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    user_agent character varying(255),
    ip_address inet,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    replaced_by_id uuid
);


--
-- Name: reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reports (
    reporter_id uuid NOT NULL,
    target_type character varying(20) NOT NULL,
    target_id uuid NOT NULL,
    reason character varying(20) NOT NULL,
    details text,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    resolved_by uuid,
    resolved_at timestamp with time zone,
    resolution_note text,
    content_removed boolean DEFAULT false NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_reports_closed_at CHECK ((((status)::text = ANY (ARRAY[('resolved'::character varying)::text, ('dismissed'::character varying)::text])) = (resolved_at IS NOT NULL))),
    CONSTRAINT ck_reports_other_has_details CHECK ((((reason)::text <> 'other'::text) OR (details IS NOT NULL))),
    CONSTRAINT ck_reports_reason CHECK (((reason)::text = ANY (ARRAY[('spam'::character varying)::text, ('offensive'::character varying)::text, ('copyright'::character varying)::text, ('misleading'::character varying)::text, ('other'::character varying)::text]))),
    CONSTRAINT ck_reports_removed_only_when_resolved CHECK (((NOT content_removed) OR ((status)::text = 'resolved'::text))),
    CONSTRAINT ck_reports_status CHECK (((status)::text = ANY (ARRAY[('open'::character varying)::text, ('reviewing'::character varying)::text, ('resolved'::character varying)::text, ('dismissed'::character varying)::text]))),
    CONSTRAINT ck_reports_target_type CHECK (((target_type)::text = ANY (ARRAY[('course'::character varying)::text, ('review'::character varying)::text, ('qa_thread'::character varying)::text, ('qa_reply'::character varying)::text])))
);


--
-- Name: reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reviews (
    course_id uuid NOT NULL,
    user_id uuid NOT NULL,
    rating integer NOT NULL,
    comment text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_reviews_comment_not_blank CHECK (((comment IS NULL) OR (length(btrim(comment)) > 0))),
    CONSTRAINT ck_reviews_rating CHECK (((rating >= 1) AND (rating <= 5)))
);


--
-- Name: streaks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.streaks (
    user_id uuid NOT NULL,
    current_streak integer NOT NULL,
    longest_streak integer NOT NULL,
    last_active_date date NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_streaks_counts CHECK (((current_streak >= 1) AND (longest_streak >= current_streak)))
);


--
-- Name: submission_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.submission_results (
    submission_id uuid NOT NULL,
    test_case_id uuid NOT NULL,
    verdict character varying(3) NOT NULL,
    run_time_ms integer,
    stdout_trunc text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_submission_results_verdict CHECK (((verdict)::text = ANY (ARRAY[('AC'::character varying)::text, ('WA'::character varying)::text, ('TLE'::character varying)::text, ('MLE'::character varying)::text, ('RE'::character varying)::text, ('CE'::character varying)::text, ('SE'::character varying)::text])))
);


--
-- Name: submissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.submissions (
    user_id uuid NOT NULL,
    exercise_id uuid NOT NULL,
    code text NOT NULL,
    language character varying(20) NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    verdict character varying(3),
    score integer,
    run_time_ms integer,
    message text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_trial boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_submissions_score CHECK (((score IS NULL) OR ((score >= 0) AND (score <= 100)))),
    CONSTRAINT ck_submissions_status CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('running'::character varying)::text, ('done'::character varying)::text, ('error'::character varying)::text]))),
    CONSTRAINT ck_submissions_verdict CHECK (((verdict IS NULL) OR ((verdict)::text = ANY (ARRAY[('AC'::character varying)::text, ('WA'::character varying)::text, ('TLE'::character varying)::text, ('MLE'::character varying)::text, ('RE'::character varying)::text, ('CE'::character varying)::text, ('SE'::character varying)::text])))),
    CONSTRAINT ck_submissions_verdict_requires_done CHECK ((((status)::text = 'done'::text) OR (verdict IS NULL)))
);


--
-- Name: test_cases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.test_cases (
    exercise_id uuid NOT NULL,
    input text DEFAULT ''::text NOT NULL,
    expected_output text NOT NULL,
    is_hidden boolean DEFAULT true NOT NULL,
    "position" integer NOT NULL,
    score_weight integer DEFAULT 1 NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_test_cases_score_weight CHECK ((score_weight > 0))
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    email character varying(255) NOT NULL,
    password_hash character varying(255),
    full_name character varying(150) NOT NULL,
    avatar_url text,
    role character varying(20) DEFAULT 'student'::character varying NOT NULL,
    oauth_provider character varying(20),
    oauth_sub character varying(255),
    email_verified_at timestamp with time zone,
    locked_at timestamp with time zone,
    last_login_at timestamp with time zone,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_users_credential CHECK (((password_hash IS NOT NULL) OR (oauth_sub IS NOT NULL))),
    CONSTRAINT ck_users_role CHECK (((role)::text = ANY (ARRAY[('student'::character varying)::text, ('instructor'::character varying)::text, ('admin'::character varying)::text])))
);


--
-- Name: video_assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.video_assets (
    storage_key character varying(500) NOT NULL,
    duration_s integer,
    hls_manifest_key text,
    status character varying(20) DEFAULT 'uploading'::character varying NOT NULL,
    error_message text,
    transcript_key text,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_video_assets_status CHECK (((status)::text = ANY (ARRAY[('uploading'::character varying)::text, ('processing'::character varying)::text, ('ready'::character varying)::text, ('failed'::character varying)::text])))
);


--
-- Name: wishlists; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wishlists (
    user_id uuid NOT NULL,
    course_id uuid NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: xp_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.xp_events (
    user_id uuid NOT NULL,
    amount integer NOT NULL,
    reason character varying(30) NOT NULL,
    ref_type character varying(30) NOT NULL,
    ref_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    CONSTRAINT ck_xp_events_amount_positive CHECK ((amount > 0)),
    CONSTRAINT ck_xp_events_reason_ref CHECK (((((reason)::text = 'lesson_completed'::text) AND ((ref_type)::text = 'lesson'::text)) OR (((reason)::text = 'quiz_passed'::text) AND ((ref_type)::text = 'quiz'::text)) OR (((reason)::text = 'exercise_solved'::text) AND ((ref_type)::text = 'code_exercise'::text))))
);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: banners banners_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.banners
    ADD CONSTRAINT banners_pkey PRIMARY KEY (id);


--
-- Name: bookmarks bookmarks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookmarks
    ADD CONSTRAINT bookmarks_pkey PRIMARY KEY (id);


--
-- Name: cart_items cart_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cart_items
    ADD CONSTRAINT cart_items_pkey PRIMARY KEY (id);


--
-- Name: carts carts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carts
    ADD CONSTRAINT carts_pkey PRIMARY KEY (id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: certificates certificates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificates
    ADD CONSTRAINT certificates_pkey PRIMARY KEY (id);


--
-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);


--
-- Name: chat_sessions chat_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_pkey PRIMARY KEY (id);


--
-- Name: code_exercises code_exercises_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.code_exercises
    ADD CONSTRAINT code_exercises_pkey PRIMARY KEY (id);


--
-- Name: coupon_courses coupon_courses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.coupon_courses
    ADD CONSTRAINT coupon_courses_pkey PRIMARY KEY (coupon_id, course_id);


--
-- Name: coupons coupons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.coupons
    ADD CONSTRAINT coupons_pkey PRIMARY KEY (id);


--
-- Name: course_embeddings course_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_embeddings
    ADD CONSTRAINT course_embeddings_pkey PRIMARY KEY (id);


--
-- Name: course_sections course_sections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_sections
    ADD CONSTRAINT course_sections_pkey PRIMARY KEY (id);


--
-- Name: courses courses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses
    ADD CONSTRAINT courses_pkey PRIMARY KEY (id);


--
-- Name: doc_chunks doc_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doc_chunks
    ADD CONSTRAINT doc_chunks_pkey PRIMARY KEY (id);


--
-- Name: enrollments enrollments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.enrollments
    ADD CONSTRAINT enrollments_pkey PRIMARY KEY (id);


--
-- Name: lesson_progress lesson_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lesson_progress
    ADD CONSTRAINT lesson_progress_pkey PRIMARY KEY (id);


--
-- Name: lessons lessons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lessons
    ADD CONSTRAINT lessons_pkey PRIMARY KEY (id);


--
-- Name: notes notes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: order_items order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: orphan_objects orphan_objects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orphan_objects
    ADD CONSTRAINT orphan_objects_pkey PRIMARY KEY (id);


--
-- Name: payment_events payment_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_events
    ADD CONSTRAINT payment_events_pkey PRIMARY KEY (id);


--
-- Name: qa_replies qa_replies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qa_replies
    ADD CONSTRAINT qa_replies_pkey PRIMARY KEY (id);


--
-- Name: qa_threads qa_threads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qa_threads
    ADD CONSTRAINT qa_threads_pkey PRIMARY KEY (id);


--
-- Name: qa_votes qa_votes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qa_votes
    ADD CONSTRAINT qa_votes_pkey PRIMARY KEY (id);


--
-- Name: quiz_attempts quiz_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_pkey PRIMARY KEY (id);


--
-- Name: quiz_questions quiz_questions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_questions
    ADD CONSTRAINT quiz_questions_pkey PRIMARY KEY (id);


--
-- Name: quizzes quizzes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: reports reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_pkey PRIMARY KEY (id);


--
-- Name: reviews reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_pkey PRIMARY KEY (id);


--
-- Name: streaks streaks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.streaks
    ADD CONSTRAINT streaks_pkey PRIMARY KEY (id);


--
-- Name: submission_results submission_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_results
    ADD CONSTRAINT submission_results_pkey PRIMARY KEY (id);


--
-- Name: submissions submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_pkey PRIMARY KEY (id);


--
-- Name: test_cases test_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.test_cases
    ADD CONSTRAINT test_cases_pkey PRIMARY KEY (id);


--
-- Name: bookmarks uq_bookmarks_user_lesson; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookmarks
    ADD CONSTRAINT uq_bookmarks_user_lesson UNIQUE (user_id, lesson_id);


--
-- Name: cart_items uq_cart_items_cart_course; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cart_items
    ADD CONSTRAINT uq_cart_items_cart_course UNIQUE (cart_id, course_id);


--
-- Name: carts uq_carts_user_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carts
    ADD CONSTRAINT uq_carts_user_id UNIQUE (user_id);


--
-- Name: certificates uq_certificates_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificates
    ADD CONSTRAINT uq_certificates_code UNIQUE (code);


--
-- Name: certificates uq_certificates_enrollment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificates
    ADD CONSTRAINT uq_certificates_enrollment UNIQUE (enrollment_id);


--
-- Name: code_exercises uq_code_exercises_lesson; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.code_exercises
    ADD CONSTRAINT uq_code_exercises_lesson UNIQUE (lesson_id);


--
-- Name: coupons uq_coupons_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.coupons
    ADD CONSTRAINT uq_coupons_code UNIQUE (code);


--
-- Name: course_sections uq_course_sections_position; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_sections
    ADD CONSTRAINT uq_course_sections_position UNIQUE (course_id, "position") DEFERRABLE INITIALLY DEFERRED;


--
-- Name: doc_chunks uq_doc_chunks_lesson_chunk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doc_chunks
    ADD CONSTRAINT uq_doc_chunks_lesson_chunk UNIQUE (lesson_id, chunk_index);


--
-- Name: enrollments uq_enrollments_user_course; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.enrollments
    ADD CONSTRAINT uq_enrollments_user_course UNIQUE (user_id, course_id);


--
-- Name: lesson_progress uq_lesson_progress_enrollment_lesson; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lesson_progress
    ADD CONSTRAINT uq_lesson_progress_enrollment_lesson UNIQUE (enrollment_id, lesson_id);


--
-- Name: lessons uq_lessons_position; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lessons
    ADD CONSTRAINT uq_lessons_position UNIQUE (section_id, "position") DEFERRABLE INITIALLY DEFERRED;


--
-- Name: order_items uq_order_items_order_course; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT uq_order_items_order_course UNIQUE (order_id, course_id);


--
-- Name: orders uq_orders_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT uq_orders_code UNIQUE (code);


--
-- Name: orphan_objects uq_orphan_objects_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orphan_objects
    ADD CONSTRAINT uq_orphan_objects_key UNIQUE (key);


--
-- Name: qa_votes uq_qa_votes_thread_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qa_votes
    ADD CONSTRAINT uq_qa_votes_thread_user UNIQUE (thread_id, user_id);


--
-- Name: quiz_questions uq_quiz_questions_position; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_questions
    ADD CONSTRAINT uq_quiz_questions_position UNIQUE (quiz_id, "position") DEFERRABLE INITIALLY DEFERRED;


--
-- Name: quizzes uq_quizzes_lesson; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT uq_quizzes_lesson UNIQUE (lesson_id);


--
-- Name: reviews uq_reviews_course_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT uq_reviews_course_user UNIQUE (course_id, user_id);


--
-- Name: streaks uq_streaks_user_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.streaks
    ADD CONSTRAINT uq_streaks_user_id UNIQUE (user_id);


--
-- Name: submission_results uq_submission_results; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_results
    ADD CONSTRAINT uq_submission_results UNIQUE (submission_id, test_case_id);


--
-- Name: test_cases uq_test_cases_position; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.test_cases
    ADD CONSTRAINT uq_test_cases_position UNIQUE (exercise_id, "position") DEFERRABLE INITIALLY DEFERRED;


--
-- Name: video_assets uq_video_assets_storage_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_assets
    ADD CONSTRAINT uq_video_assets_storage_key UNIQUE (storage_key);


--
-- Name: wishlists uq_wishlists_user_course; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wishlists
    ADD CONSTRAINT uq_wishlists_user_course UNIQUE (user_id, course_id);


--
-- Name: xp_events uq_xp_events_ref; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.xp_events
    ADD CONSTRAINT uq_xp_events_ref UNIQUE (user_id, reason, ref_type, ref_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: video_assets video_assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_assets
    ADD CONSTRAINT video_assets_pkey PRIMARY KEY (id);


--
-- Name: wishlists wishlists_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wishlists
    ADD CONSTRAINT wishlists_pkey PRIMARY KEY (id);


--
-- Name: xp_events xp_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.xp_events
    ADD CONSTRAINT xp_events_pkey PRIMARY KEY (id);


--
-- Name: ix_banners_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_banners_active ON public.banners USING btree ("position") WHERE is_active;


--
-- Name: ix_cart_items_cart_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cart_items_cart_created ON public.cart_items USING btree (cart_id, created_at DESC);


--
-- Name: ix_categories_parent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_categories_parent_id ON public.categories USING btree (parent_id);


--
-- Name: ix_chat_messages_session_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_messages_session_created ON public.chat_messages USING btree (session_id, created_at);


--
-- Name: ix_chat_sessions_user_course; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_sessions_user_course ON public.chat_sessions USING btree (user_id, course_id);


--
-- Name: ix_course_embeddings_embedding; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_course_embeddings_embedding ON public.course_embeddings USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: ix_courses_category_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_category_id ON public.courses USING btree (category_id);


--
-- Name: ix_courses_instructor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_instructor_id ON public.courses USING btree (instructor_id);


--
-- Name: ix_courses_listing; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_listing ON public.courses USING btree (status, published_at DESC) WHERE (deleted_at IS NULL);


--
-- Name: ix_courses_rating; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_rating ON public.courses USING btree (status, rating_avg DESC) WHERE (deleted_at IS NULL);


--
-- Name: ix_courses_search_vector; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_search_vector ON public.courses USING gin (search_vector);


--
-- Name: ix_doc_chunks_course_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_doc_chunks_course_id ON public.doc_chunks USING btree (course_id);


--
-- Name: ix_doc_chunks_embedding; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_doc_chunks_embedding ON public.doc_chunks USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: ix_enrollments_course_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_enrollments_course_created ON public.enrollments USING btree (course_id, created_at);


--
-- Name: ix_enrollments_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_enrollments_user_id ON public.enrollments USING btree (user_id);


--
-- Name: ix_notes_user_lesson; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notes_user_lesson ON public.notes USING btree (user_id, lesson_id);


--
-- Name: ix_notifications_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_user_created ON public.notifications USING btree (user_id, created_at DESC);


--
-- Name: ix_notifications_user_unread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_user_unread ON public.notifications USING btree (user_id, created_at DESC) WHERE (read_at IS NULL);


--
-- Name: ix_order_items_course_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_items_course_id ON public.order_items USING btree (course_id);


--
-- Name: ix_orders_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_orders_user_created ON public.orders USING btree (user_id, created_at DESC);


--
-- Name: ix_payment_events_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_events_order_id ON public.payment_events USING btree (order_id);


--
-- Name: ix_qa_replies_thread_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_qa_replies_thread_created ON public.qa_replies USING btree (thread_id, created_at);


--
-- Name: ix_qa_threads_lesson_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_qa_threads_lesson_created ON public.qa_threads USING btree (lesson_id, created_at);


--
-- Name: ix_quiz_attempts_quiz_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quiz_attempts_quiz_user ON public.quiz_attempts USING btree (quiz_id, user_id, started_at DESC);


--
-- Name: ix_refresh_tokens_replaced_by_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_replaced_by_id ON public.refresh_tokens USING btree (replaced_by_id);


--
-- Name: ix_refresh_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_user_id ON public.refresh_tokens USING btree (user_id);


--
-- Name: ix_reports_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reports_status ON public.reports USING btree (status, created_at);


--
-- Name: ix_reports_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reports_target ON public.reports USING btree (target_type, target_id);


--
-- Name: ix_reviews_course_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reviews_course_created ON public.reviews USING btree (course_id, created_at DESC);


--
-- Name: ix_submissions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_submissions_status ON public.submissions USING btree (status) WHERE ((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('running'::character varying)::text]));


--
-- Name: ix_submissions_user_exercise; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_submissions_user_exercise ON public.submissions USING btree (user_id, exercise_id, created_at DESC) WHERE (is_trial = false);


--
-- Name: ix_users_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_role ON public.users USING btree (role);


--
-- Name: ix_wishlists_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_wishlists_user_created ON public.wishlists USING btree (user_id, created_at DESC);


--
-- Name: ix_xp_events_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_xp_events_user_created ON public.xp_events USING btree (user_id, created_at);


--
-- Name: uq_categories_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_categories_slug ON public.categories USING btree (slug);


--
-- Name: uq_course_embeddings_course_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_course_embeddings_course_id ON public.course_embeddings USING btree (course_id);


--
-- Name: uq_courses_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_courses_slug ON public.courses USING btree (slug);


--
-- Name: uq_orders_provider_txn; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_orders_provider_txn ON public.orders USING btree (payment_provider, provider_txn_id) WHERE (provider_txn_id IS NOT NULL);


--
-- Name: uq_quiz_attempts_open; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_quiz_attempts_open ON public.quiz_attempts USING btree (quiz_id, user_id) WHERE (submitted_at IS NULL);


--
-- Name: uq_refresh_tokens_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_refresh_tokens_token_hash ON public.refresh_tokens USING btree (token_hash);


--
-- Name: uq_reports_pending_per_reporter; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_reports_pending_per_reporter ON public.reports USING btree (reporter_id, target_type, target_id) WHERE ((status)::text = ANY (ARRAY[('open'::character varying)::text, ('reviewing'::character varying)::text]));


--
-- Name: uq_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_users_email ON public.users USING btree (email);


--
-- Name: uq_users_oauth; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_users_oauth ON public.users USING btree (oauth_provider, oauth_sub) WHERE (oauth_sub IS NOT NULL);


--
-- Name: courses courses_search_vector_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER courses_search_vector_update BEFORE INSERT OR UPDATE OF title, subtitle, description ON public.courses FOR EACH ROW EXECUTE FUNCTION public.courses_search_vector_refresh();


--
-- Name: bookmarks bookmarks_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookmarks
    ADD CONSTRAINT bookmarks_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: bookmarks bookmarks_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookmarks
    ADD CONSTRAINT bookmarks_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: cart_items cart_items_cart_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cart_items
    ADD CONSTRAINT cart_items_cart_id_fkey FOREIGN KEY (cart_id) REFERENCES public.carts(id) ON DELETE CASCADE;


--
-- Name: cart_items cart_items_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cart_items
    ADD CONSTRAINT cart_items_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: carts carts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carts
    ADD CONSTRAINT carts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: categories categories_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.categories(id) ON DELETE RESTRICT;


--
-- Name: certificates certificates_enrollment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificates
    ADD CONSTRAINT certificates_enrollment_id_fkey FOREIGN KEY (enrollment_id) REFERENCES public.enrollments(id) ON DELETE RESTRICT;


--
-- Name: chat_messages chat_messages_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id) ON DELETE CASCADE;


--
-- Name: chat_sessions chat_sessions_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: chat_sessions chat_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: code_exercises code_exercises_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.code_exercises
    ADD CONSTRAINT code_exercises_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: coupon_courses coupon_courses_coupon_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.coupon_courses
    ADD CONSTRAINT coupon_courses_coupon_id_fkey FOREIGN KEY (coupon_id) REFERENCES public.coupons(id) ON DELETE CASCADE;


--
-- Name: coupon_courses coupon_courses_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.coupon_courses
    ADD CONSTRAINT coupon_courses_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: course_embeddings course_embeddings_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_embeddings
    ADD CONSTRAINT course_embeddings_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: course_sections course_sections_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_sections
    ADD CONSTRAINT course_sections_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: courses courses_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses
    ADD CONSTRAINT courses_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE RESTRICT;


--
-- Name: courses courses_instructor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses
    ADD CONSTRAINT courses_instructor_id_fkey FOREIGN KEY (instructor_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: doc_chunks doc_chunks_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doc_chunks
    ADD CONSTRAINT doc_chunks_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: doc_chunks doc_chunks_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doc_chunks
    ADD CONSTRAINT doc_chunks_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: enrollments enrollments_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.enrollments
    ADD CONSTRAINT enrollments_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE RESTRICT;


--
-- Name: enrollments enrollments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.enrollments
    ADD CONSTRAINT enrollments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: lesson_progress lesson_progress_enrollment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lesson_progress
    ADD CONSTRAINT lesson_progress_enrollment_id_fkey FOREIGN KEY (enrollment_id) REFERENCES public.enrollments(id) ON DELETE CASCADE;


--
-- Name: lesson_progress lesson_progress_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lesson_progress
    ADD CONSTRAINT lesson_progress_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: lessons lessons_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lessons
    ADD CONSTRAINT lessons_section_id_fkey FOREIGN KEY (section_id) REFERENCES public.course_sections(id) ON DELETE CASCADE;


--
-- Name: lessons lessons_video_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lessons
    ADD CONSTRAINT lessons_video_asset_id_fkey FOREIGN KEY (video_asset_id) REFERENCES public.video_assets(id) ON DELETE SET NULL;


--
-- Name: notes notes_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: notes notes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: order_items order_items_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE RESTRICT;


--
-- Name: order_items order_items_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id) ON DELETE CASCADE;


--
-- Name: orders orders_coupon_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_coupon_id_fkey FOREIGN KEY (coupon_id) REFERENCES public.coupons(id) ON DELETE SET NULL;


--
-- Name: orders orders_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: payment_events payment_events_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_events
    ADD CONSTRAINT payment_events_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id) ON DELETE CASCADE;


--
-- Name: qa_replies qa_replies_thread_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qa_replies
    ADD CONSTRAINT qa_replies_thread_id_fkey FOREIGN KEY (thread_id) REFERENCES public.qa_threads(id) ON DELETE CASCADE;


--
-- Name: qa_replies qa_replies_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qa_replies
    ADD CONSTRAINT qa_replies_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: qa_threads qa_threads_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qa_threads
    ADD CONSTRAINT qa_threads_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: qa_threads qa_threads_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qa_threads
    ADD CONSTRAINT qa_threads_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: qa_votes qa_votes_thread_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qa_votes
    ADD CONSTRAINT qa_votes_thread_id_fkey FOREIGN KEY (thread_id) REFERENCES public.qa_threads(id) ON DELETE CASCADE;


--
-- Name: qa_votes qa_votes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qa_votes
    ADD CONSTRAINT qa_votes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: quiz_attempts quiz_attempts_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_quiz_id_fkey FOREIGN KEY (quiz_id) REFERENCES public.quizzes(id) ON DELETE CASCADE;


--
-- Name: quiz_attempts quiz_attempts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: quiz_questions quiz_questions_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_questions
    ADD CONSTRAINT quiz_questions_quiz_id_fkey FOREIGN KEY (quiz_id) REFERENCES public.quizzes(id) ON DELETE CASCADE;


--
-- Name: quizzes quizzes_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_replaced_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_replaced_by_id_fkey FOREIGN KEY (replaced_by_id) REFERENCES public.refresh_tokens(id) ON DELETE SET NULL;


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: reports reports_reporter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_reporter_id_fkey FOREIGN KEY (reporter_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: reports reports_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: reviews reviews_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: reviews reviews_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: streaks streaks_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.streaks
    ADD CONSTRAINT streaks_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: submission_results submission_results_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_results
    ADD CONSTRAINT submission_results_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id) ON DELETE CASCADE;


--
-- Name: submission_results submission_results_test_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_results
    ADD CONSTRAINT submission_results_test_case_id_fkey FOREIGN KEY (test_case_id) REFERENCES public.test_cases(id) ON DELETE CASCADE;


--
-- Name: submissions submissions_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.code_exercises(id) ON DELETE CASCADE;


--
-- Name: submissions submissions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: test_cases test_cases_exercise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.test_cases
    ADD CONSTRAINT test_cases_exercise_id_fkey FOREIGN KEY (exercise_id) REFERENCES public.code_exercises(id) ON DELETE CASCADE;


--
-- Name: wishlists wishlists_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wishlists
    ADD CONSTRAINT wishlists_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: wishlists wishlists_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wishlists
    ADD CONSTRAINT wishlists_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: xp_events xp_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.xp_events
    ADD CONSTRAINT xp_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--


