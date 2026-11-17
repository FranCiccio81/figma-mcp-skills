---
name: frontend-security
description: >-
  Reviews and hardens web frontend security: XSS prevention and safe rendering,
  Content Security Policy and security headers, authentication token and session
  handling, CSRF, third-party scripts and supply chain, secrets in client code,
  sensitive data in logs and analytics, and secure forms for regulated domains. Use
  when the user builds or reviews a web frontend handling user data, authentication or
  payments, asks about XSS, CSP or CSRF, or prepares a security review.
metadata:
  domain: engineering
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Frontend security

This skill supports secure engineering; it does not replace a security team's review or penetration testing in regulated contexts.

## When to use

* Building or reviewing frontends that handle personal, financial or authentication data.
* Adding third-party scripts, rendering user or CMS content, configuring headers.

## Inputs

* Framework, rendering model (SSR, SPA), authentication approach, hosting and header control, third-party scripts, data classification.

## Procedure

1. **Rendering safety.** Rely on the framework's escaping; treat every raw HTML sink (`dangerouslySetInnerHTML`, `innerHTML`, `v-html`) as a finding unless the content is sanitized with a maintained sanitizer; validate URLs before using them in `href` or `src` (block `javascript:`).
2. **Content Security Policy.** Prefer nonce- or hash-based policies, `object-src 'none'`, `base-uri 'none'` or `'self'`, `frame-ancestors` to prevent clickjacking; roll out in report-only mode first.
3. **Headers:** HSTS, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`.
4. **Sessions and tokens.** Prefer HttpOnly, Secure, SameSite cookies managed by the server over tokens in `localStorage`; short lifetimes; logout invalidates server-side.
5. **CSRF** protection for cookie-authenticated state changes (SameSite plus tokens or framework protection).
6. **Secrets.** No secrets in client bundles or public environment variables; anything shipped to the browser is public.
7. **Third parties and supply chain.** Inventory scripts and packages; lockfiles; dependency audits in CI; Subresource Integrity for static third-party files; least privilege for tag managers.
8. **Data exposure.** No personal or financial data in URLs, logs, analytics events or error reports; mask sensitive fields; disable autocomplete only where required.
9. **Verify:** automated scanning (dependency audit, CSP evaluator, header check) plus manual review of sinks; record residual risks.

## Output

Findings table (issue, location, risk, likelihood, impact, fix, reference), recommended headers and CSP, and residual risk list.

## Edge cases

* Legacy inline scripts block a strict CSP: plan a migration (nonces, hashes) rather than adding `unsafe-inline`.
* Embedded payment or identity providers: follow their integration guides; keep their iframes isolated.
* Regulated data: involve security and compliance owners; do not assert regulatory compliance.

## Acceptance criteria

* Every raw HTML sink is removed or justified with sanitization.
* No secret is present in client code or public configuration.
* Findings reference a recognized source (OWASP or MDN) and state a fix.

## Sources

* OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/
* OWASP Top 10: https://owasp.org/
* MDN Web Docs, web security: https://developer.mozilla.org/
