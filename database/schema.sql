

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    message_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT NOT NULL,
    turn_index  INTEGER NOT NULL DEFAULT 0,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    UNIQUE(session_id, turn_index)
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);

CREATE TABLE IF NOT EXISTS retrieval_logs (
    log_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     TEXT NOT NULL,
    retrieval_info TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
