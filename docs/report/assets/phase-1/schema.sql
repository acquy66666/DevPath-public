--
-- PostgreSQL database dump
--

\restrict Q4OmltwxfKkyk6BjAZx3soI3ZzMdXuLH4PxeXKUYJUerAvr9p7G67Q9yEQmY5MO

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


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
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
    CONSTRAINT ck_courses_level CHECK (((level)::text = ANY ((ARRAY['beginner'::character varying, 'intermediate'::character varying, 'advanced'::character varying])::text[]))),
    CONSTRAINT ck_courses_price_non_negative CHECK ((price >= (0)::numeric)),
    CONSTRAINT ck_courses_published_at CHECK ((((status)::text <> 'published'::text) OR (published_at IS NOT NULL))),
    CONSTRAINT ck_courses_rating_range CHECK ((((rating_avg >= (0)::numeric) AND (rating_avg <= (5)::numeric)) AND (rating_count >= 0))),
    CONSTRAINT ck_courses_rejection_reason CHECK ((((status)::text <> 'rejected'::text) OR (rejection_reason IS NOT NULL))),
    CONSTRAINT ck_courses_status CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'pending_review'::character varying, 'published'::character varying, 'rejected'::character varying])::text[])))
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
    CONSTRAINT ck_users_role CHECK (((role)::text = ANY ((ARRAY['student'::character varying, 'instructor'::character varying, 'admin'::character varying])::text[])))
);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: courses courses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses
    ADD CONSTRAINT courses_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_categories_parent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_categories_parent_id ON public.categories USING btree (parent_id);


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
-- Name: ix_users_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_role ON public.users USING btree (role);


--
-- Name: uq_categories_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_categories_slug ON public.categories USING btree (slug);


--
-- Name: uq_courses_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_courses_slug ON public.courses USING btree (slug);


--
-- Name: uq_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_users_email ON public.users USING btree (email);


--
-- Name: uq_users_oauth; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_users_oauth ON public.users USING btree (oauth_provider, oauth_sub) WHERE (oauth_sub IS NOT NULL);


--
-- Name: categories categories_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.categories(id) ON DELETE RESTRICT;


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
-- PostgreSQL database dump complete
--

\unrestrict Q4OmltwxfKkyk6BjAZx3soI3ZzMdXuLH4PxeXKUYJUerAvr9p7G67Q9yEQmY5MO

