# Failure and Recovery Verification

## Test-backed failure cases

- startup rejects any trading flag set to true;
- runtime reads reject a missing/wrong read credential;
- mutations and scheduler calls reject missing/wrong credentials;
- synthetic replay remains disabled by default;
- provider failure preserves the previous successful data;
- Finviz rate limits use bounded retries;
- Telegram failure preserves queued work and enforces an attempt limit;
- scheduler exceptions record a failed event and release no duplicate run;
- missing/stale fields reduce confidence and never become invented values;
- backup refuses the active path and overwrite;
- backup integrity and isolated restore rehearsal are test-backed;
- unknown outcome evidence remains unavailable, not zero.

## External recovery gates

Production backup retention, encryption, Supabase isolated restore, protected
runtime rollback and deployed alerting are not proven by local tests. They must
remain pending until executed on an approved target with a usable backup.
