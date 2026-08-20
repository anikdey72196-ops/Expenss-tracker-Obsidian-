## 2024-08-20 - [Fix] Incomplete CSRF Protection on Delete Action (Re-fixed)
**Vulnerability:** The `delete_expense` endpoint in `templates/history.html` used a GET link (an `<a>` tag), breaking because the backend endpoint correctly required POST to avoid CSRF and arbitrary deletion.
**Learning:** Security updates requiring POST methods (like CSRF implementations) must have corresponding frontend template changes, converting links to forms containing the CSRF token.
**Prevention:** Always verify UI components and frontend templates whenever an endpoint's allowed methods are restricted.

## 2024-08-20 - [Fix] Missing Rate Limiting on Authentication Endpoints
**Vulnerability:** The `/login` endpoints in both `app.py` and `auth.py` lacked rate limiting, rendering the application vulnerable to brute-force and credential-stuffing attacks.
**Learning:** Authentication endpoints are prime targets for automated attacks. They must implement rate limiting based on IP or User-Agent to throttle repeated failed attempts. When implementing in-memory limiting (e.g. using a dictionary), the structure must be size-bounded to prevent memory exhaustion DoS attacks if an attacker spoofs many IPs.
**Prevention:** Use a distributed store like Redis for production rate limiting, or enforce strict dictionary size bounds if using in-memory implementations.
