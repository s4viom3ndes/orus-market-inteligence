-- Orus auth schema. SQLite-compatible; use as reference pra migracao Postgres.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name          TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS ml_accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ml_user_id      INTEGER NOT NULL,
    ml_nickname     TEXT,
    ml_email        TEXT,
    site_id         TEXT NOT NULL DEFAULT 'MLB',
    is_active       INTEGER NOT NULL DEFAULT 1,
    linked_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, ml_user_id)
);

CREATE TABLE IF NOT EXISTS ml_token_sets (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ml_account_id    INTEGER NOT NULL REFERENCES ml_accounts(id) ON DELETE CASCADE,
    access_token     TEXT NOT NULL,
    refresh_token    TEXT,
    token_type       TEXT NOT NULL DEFAULT 'Bearer',
    scope            TEXT,
    obtained_at      INTEGER NOT NULL,
    expires_at       INTEGER NOT NULL,
    UNIQUE(ml_account_id)
);

CREATE TABLE IF NOT EXISTS client_skus (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ml_account_id       INTEGER NOT NULL REFERENCES ml_accounts(id) ON DELETE CASCADE,
    sku                 TEXT NOT NULL,
    catalog_product_id  TEXT NOT NULL,
    category_id         TEXT,
    product_hint        TEXT,
    current_price       REAL NOT NULL,
    min_price           REAL NOT NULL,
    max_price           REAL,
    target_position     INTEGER NOT NULL DEFAULT 0,
    strategy            TEXT NOT NULL DEFAULT 'beat_winner',
    beat_delta          REAL NOT NULL DEFAULT 0.01,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ml_account_id, sku)
);
CREATE INDEX IF NOT EXISTS idx_client_skus_account ON client_skus(ml_account_id);

CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at    TIMESTAMP NOT NULL,
    revoked_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
