---
name: frontend-security
description: >-
  Reviews and hardens frontend code against common web risks: XSS and unsafe HTML rendering,
  Content Security Policy, token and session storage, CSRF, clickjacking, open redirects, third-party
  scripts and dependencies, secrets in bundles, and personal data in logs and analytics, with
  OWASP guidance. Use when building or reviewing auth flows, forms, rich text rendering, payment or
  account screens, third-party integrations, or when asked for a frontend security review. Do not
  use as a substitute for a professional penetration test or backend security review.
license: MIT
metadata:
  version: "1.0.0"
  domain: engineering
  status: beta
  trust: internal
  sources: "OWASP,WEB-MDN,REACT-DOCS"
  platforms: "web"
  last-reviewed: "2026-11-17"
---

# Frontend security

The browser is hostile territory: anything shipped to it is public, and anything rendered from
input can execute.

## When to use

- Reviewing code that renders user or third-party content.
- Implementing login, session, payment or account management UI.
- Adding third-party scripts, SDKs or dependencies.

## Inputs

- Code, build configuration, HTTP headers or hosting configuration.
- Authentication architecture (cookies, tokens, identity provider).
- Data classification (personal, financial).

## Workflow

1. **Rendering:** rely on framework escaping; flag every `dangerouslySetInnerHTML`, `innerHTML`,
   `v-html` or equivalent; sanitise with a maintained sanitiser when HTML is unavoidable; never
   build URLs with `javascript:`; validate URLs before using them in `href` or redirects.
2. **Content Security Policy:** recommend a strict CSP (nonces or hashes, no `unsafe-inline` for
   scripts), `frame-ancestors` against clickjacking, and report-only rollout first.
3. **Sessions and tokens:** prefer `HttpOnly`, `Secure`, `SameSite` cookies for session tokens
   over storage readable by JavaScript; short-lived access tokens; logout clears server and client state.
4. **CSRF:** with cookie auth, require SameSite plus CSRF tokens or other server-verified
   protections on state-changing requests.
5. **Secrets:** no API secrets, private keys or internal endpoints in client bundles or
   environment variables exposed to the client.
6. **Third parties and dependencies:** inventory scripts and SDKs, load with Subresource
   Integrity where possible, restrict with CSP; check dependencies for known vulnerabilities in CI.
7. **Personal data:** no personal or financial data in URLs, logs, error trackers or analytics
   events; mask sensitive fields; disable autocomplete only where policy requires it.
8. **Input handling:** client validation for usability only; the server re-validates everything.
9. **Report** findings with risk, location, exploit scenario, severity and fix, mapped to the
   relevant OWASP category or cheat sheet.

## Outputs

Security review table (ID, location, risk, scenario, severity, fix, reference) and concrete code
or configuration changes.

## Edge cases

- **Markdown or rich text from users:** render with a safe renderer and sanitiser; disallow raw HTML.
- **Embedded webviews in mobile apps:** apply the same rules plus message-bridge validation.
- **Feature flags or config fetched at runtime:** treat as untrusted input.
- **Uncertain exploitability:** report as a risk with the assumption stated, not as a confirmed vulnerability.

## Acceptance criteria

- [ ] Every raw HTML rendering point is listed and justified or fixed.
- [ ] Session tokens are not readable by JavaScript unless an explicit, reviewed exception exists.
- [ ] No secrets or personal data in client bundles, URLs, logs or analytics.
- [ ] CSP and frame-ancestors recommendations are given.
- [ ] Findings are mapped to OWASP references.

## Sources

- OWASP and the OWASP Cheat Sheet Series: https://owasp.org/ and https://cheatsheetseries.owasp.org/
- MDN Web Docs, web security and CSP: https://developer.mozilla.org/
- React documentation on dangerouslySetInnerHTML: https://react.dev/
