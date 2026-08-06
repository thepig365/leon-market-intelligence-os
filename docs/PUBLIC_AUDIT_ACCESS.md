# Public audit access

LMIO keeps its operating dashboard, runtime API, licensed market data, account
details, watchlists and research records private. External AI tools can audit the
product through the server-rendered `/public-audit` route without authentication.

The public route contains only:

- the product purpose and no-trading boundary;
- the 13-module product map;
- approved source categories;
- security and data-handling safeguards; and
- a link to the existing protected operator sign-in.

The route is intentionally excluded from search indexing. Direct URL retrieval
does not require client-side JavaScript. It must never import the authenticated
runtime client, expose current licensed Finviz records, or return credentials.

Publishing or materially expanding this route requires Leon's approval under the
enterprise public-output gate. The authenticated dashboard must not be made
anonymous as a shortcut.
