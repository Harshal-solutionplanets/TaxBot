-- =============================================
-- TABLE 1: taxbot_users
-- Stores verified taxsutra.com users who have
-- accessed TaxBot at least once.
-- =============================================
CREATE TABLE IF NOT EXISTS taxbot_users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    taxsutra_id    TEXT NOT NULL UNIQUE,  -- user.id from taxsutra.com JWT
    email          TEXT NOT NULL UNIQUE,
    full_name      TEXT,
    plan           TEXT DEFAULT 'basic',  -- 'basic', 'premium', etc.
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- TABLE 2: taxbot_sessions
-- Each conversation thread. Replaces SQLite
-- sessions table.
-- =============================================
CREATE TABLE IF NOT EXISTS taxbot_sessions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES taxbot_users(id) ON DELETE CASCADE,
    title        TEXT NOT NULL DEFAULT 'New Chat',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- TABLE 3: taxbot_messages
-- Individual messages in each session.
-- =============================================
CREATE TABLE IF NOT EXISTS taxbot_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES taxbot_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    source      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- TABLE 4: taxbot_query_usage
-- Tracks daily query count per user for the
-- 3-queries-per-day rate limit.
-- =============================================
CREATE TABLE IF NOT EXISTS taxbot_query_usage (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES taxbot_users(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    count      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, usage_date)   -- one row per user per day
);

-- =============================================
-- INDEXES (for query performance)
-- =============================================
CREATE INDEX IF NOT EXISTS idx_sessions_user_id     ON taxbot_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_session_id  ON taxbot_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_usage_user_date      ON taxbot_query_usage(user_id, usage_date);