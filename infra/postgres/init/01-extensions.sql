-- Runs once, on an empty data directory. Extensions belong here rather than in
-- an Alembic migration: CREATE EXTENSION needs superuser, which the application
-- role must not have.
CREATE EXTENSION IF NOT EXISTS vector;      -- RAG embeddings (pgvector)
CREATE EXTENSION IF NOT EXISTS unaccent;    -- Vietnamese full-text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- fuzzy course-title matching
