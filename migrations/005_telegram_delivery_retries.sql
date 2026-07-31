-- LMIO runtime schema v5.
-- Preserve Telegram delivery attempts so queued and failed messages can be
-- retried without creating duplicate outbox records.

ALTER TABLE telegram_deliveries
ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE telegram_deliveries
ADD COLUMN last_attempt_at TIMESTAMP;

INSERT INTO schema_versions(version) VALUES (5);
