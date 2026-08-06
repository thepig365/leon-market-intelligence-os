# Telegram Verification Report

Status: **awaiting_fresh_rc1_evidence**

## Implemented controls

- webhook secret validation;
- one authorised private chat only;
- `/status`, `/health`, `/top3`, `/top10`, `/news`, `/help` and ticker queries;
- ticker lookup through the authorised Finviz adapter;
- deduplication, bounded retries, atomic claims and an auditable outbox;
- delivery failure does not interrupt the research pipeline;
- no group use, no trade execution and no secret returned to the browser.

## Required fresh proof

From the protected RC1 runtime, send a non-sensitive test message, confirm the
provider message identifier is stored, query `/status` and one ticker from the
approved chat, and verify wrong-secret/wrong-chat rejection. No token or chat
identifier may appear in the report. Until then the UI must show configured or
awaiting verification, never ready.
