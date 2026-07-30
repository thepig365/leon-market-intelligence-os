# LMIO Dashboard

Chinese-first, read-only Next.js dashboard for Leon Market Intelligence OS.
It implements the 13 dashboard areas required by the governing specification
and reads versioned evidence from the LMIO FastAPI runtime.

The dashboard cannot execute an order. It does not receive the LMIO
administrator key or any provider credential.

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

`LMIO_API_BASE_URL` is read only by the Next.js server. A protected deployment
must point it at the private FastAPI service and place both applications behind
the approved identity and network boundary.
