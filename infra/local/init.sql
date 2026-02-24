-- init.sql — bootstrap schema for local development
-- Runs automatically on first docker-compose up.

CREATE TABLE IF NOT EXISTS events (
    id               BIGSERIAL PRIMARY KEY,
    event_id         UUID         NOT NULL UNIQUE,
    aggregate_id     VARCHAR(128) NOT NULL DEFAULT '',
    event_type       VARCHAR(64)  NOT NULL,
    payload          JSONB        NOT NULL DEFAULT '{}',
    actor            VARCHAR(128) NOT NULL DEFAULT 'system',
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    idempotency_key  VARCHAR(128) UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_created ON events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_aggregate ON events (aggregate_id);
