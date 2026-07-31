# Research Workers

LMIO calculations, rankings, valuations, state transitions and approvals are
deterministic application responsibilities. A research worker may only
summarise supplied evidence. Its output is supporting material, not a decision.

## OpenAI Responses API adapter

`OpenAIResearchWorker` is server-side only and disabled by default. It requires
both `OPENAI_API_KEY` and `LMIO_OPENAI_MODEL`; no model is selected by the
repository.

Safety properties:

- the key is read from the server environment and is never returned by health
  endpoints;
- `store` is always `false`;
- only the evidence object supplied by LMIO is sent;
- no conversation transcript is sent;
- no web search, file search, external tool or computer-use capability is
  enabled;
- output must match the strict `ResearchSynthesis` JSON schema;
- model and prompt versions are recorded;
- the adapter cannot approve candidates, mutate permanent memory or create an
  order;
- configuration is reported as `configured_not_verified` until a separate live
  debug records a successful response.

Activation requires an approved model, API credential, usage budget and live
debug. Adding the adapter does not activate or spend on the API.

## Kimi manual workflow

The Master Spec allows a Kimi adapter or a documented manual integration. V1
uses the manual route because no approved server API is configured.

1. Build a minimal packet with `build_kimi_manual_packet`.
2. Give only that packet to the authorised operator.
3. Paste the returned JSON into the controlled import path.
4. Validate it with `validate_kimi_manual_output`.
5. Compare every claim with the packet's source URLs.
6. Keep the result as draft research until human review.

Malformed output, unsupported facts and confidence outside 0–1 are rejected.
Full chats, passwords, tokens and unrelated company information must not be
included.

## Provenance

The Responses API request shape follows the official OpenAI API reference:
Bearer authentication, server-side environment secrets, `store: false` and
`text.format.type: json_schema`. Production activation must re-check the
current official documentation and pin an approved model snapshot.
