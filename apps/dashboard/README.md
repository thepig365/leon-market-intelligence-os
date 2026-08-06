# LMIO Dashboard

The first screen uses the operating command-centre API. Non-operational data is
visibly watermarked; code, fixture and live states are not conflated.

Chinese-first, read-only Next.js dashboard for Leon Market Intelligence OS.
It implements the 13 dashboard areas required by the governing specification
and reads versioned evidence from the LMIO FastAPI runtime.

Every area has a purpose-built, Chinese-first presentation. The operator sees
plain-language conclusions, scores, risks, confirmations and next actions.
Raw JSON and technical runtime records remain available to the audit layer but
are intentionally excluded from the normal working interface.

The dashboard cannot execute an order. It does not receive the LMIO
administrator key, Supabase service-role key or any provider credential. It
reuses the approved Bayview Supabase identity and requires active private-beta
claims with an owner, operator or reviewer role.

## Local use

Start the Python runtime from the repository root:

```bash
uv run uvicorn lmio.main:app --host 127.0.0.1 --port 8000
```

Then start the dashboard:

```bash
cd apps/dashboard
cp .env.example .env.local
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`.

## Verification

```bash
npm run lint
npm run typecheck
npm test
npm run build
npm audit
```

`LMIO_API_BASE_URL` and `LMIO_READ_API_KEY` are read only by the Next.js
server. `NEXT_PUBLIC_SUPABASE_URL` and
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` support browser authentication; the
publishable key is not a service-role key. A protected deployment must point to
the private FastAPI service and use the same Bayview identity claims as Bayview
OS.
