## 2024-07-10 - [Fix] Hardcoded Flask Secret Key
**Vulnerability:** The Flask application `app.py` contained a hardcoded `app.secret_key = "your_secret_key"`.
**Learning:** Hardcoded secret keys allow attackers to forge session cookies, leading to unauthorized access and session hijacking.
**Prevention:** Always use environment variables for sensitive configuration like secret keys, with a secure fallback like `os.urandom(24)` if necessary.

## 2024-07-11 - [Fix] Missing Global CSRF Protection and Unsafe GET State Mutation
**Vulnerability:** The Flask application `app.py` lacked CSRF protection on forms, and the `/delete_expense/<int:id>` endpoint allowed state mutations via GET requests, which could lead to cross-site request forgery attacks enabling unauthorized expense deletion.
**Learning:** State-changing actions like deletes must never be exposed via GET routes as they can be triggered trivially (e.g., via `<img>` tags). Furthermore, global CSRF protection ensures all POST/PUT/DELETE requests validate a token matching the session.
**Prevention:** Use POST for all state-changing endpoints and employ a library like `flask_wtf.csrf.CSRFProtect` alongside passing `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>` in all forms.

## 2024-07-12 - [Fix] Inadequate Expense Amount Validation (NaN, Infinity, Negative)
**Vulnerability:** The application previously relied solely on Python's `float()` to validate expense amounts. `float()` accepts inputs like `"inf"`, `"nan"`, and negative numbers, which could be exploited to bypass logical checks, corrupt financial calculations (like dashboard stats or total tracking), or cause unexpected logic crashes when dealing with extreme values.
**Learning:** Never assume type coercion functions like `float()` act as comprehensive boundary validators. Python's `float()` is particularly forgiving and accommodates non-finite representations, which can cause subtle logic bugs if persisted in databases without further checks.
**Prevention:** Implement explicit boundary and finite checks (`math.isinf()`, `math.isnan()`, `>= 0`, `<= upper_limit`) after converting strings to floats, especially in financial or counting contexts.

## 2026-07-13 - [Fix] Insecure Database Connections (MitM Risk)
**Vulnerability:** The application configured SQLAlchemy to connect to external databases using `ssl.CERT_NONE` and `check_hostname: False`. This completely disabled SSL certificate validation, rendering the application vulnerable to Man-in-the-Middle (MitM) attacks where an attacker could intercept and potentially modify sensitive database traffic.
**Learning:** Managed database services (like Aiven.io, which this project uses) require SSL. However, explicitly disabling certificate verification defeats the purpose of SSL. When connecting to managed databases, we must use the correct CA bundle path to verify the identity of the database server securely.
**Prevention:** Always enforce `ssl.CERT_REQUIRED` and `check_hostname: True` for database connections outside of localhost. Explicitly specify the CA bundle path (e.g., `/etc/pki/tls/certs/ca-bundle.crt` for Amazon Linux/Vercel environments) to ensure the server's certificate can be properly verified.

## 2026-07-14 - [Fix] Information Exposure via Error Messages
**Vulnerability:** The application was catching database connection exceptions during user registration and login, and exposing the internal details `DB_HOST`, `DB_PORT`, and the raw exception string directly to the user via UI flash messages. This is a critical information disclosure.
**Learning:** Exposing raw exception strings or database connection details to end users leaks sensitive infrastructure information that an attacker can use for reconnaissance (e.g. knowing internal network structure or database versions/errors).
**Prevention:** Never expose internal exception details, stack traces, or configuration variables in user-facing error messages. Always log the detailed error internally (`app.logger.error()`) and present a safe, generic error message (e.g., "An unexpected error occurred") to the user.

## 2026-07-15 - [Fix] Incomplete CSRF Protection on Delete Action
**Vulnerability:** The `delete_expense` endpoint was previously updated to use POST methods to prevent CSRF, but the frontend still used a GET link. This caused the UI to break with a 405 error and the delete action to remain broken and not correctly protected with a CSRF token in the UI.
**Learning:** When changing the allowed HTTP methods of an endpoint (e.g. GET -> POST) for security reasons like CSRF protection, you must also update all frontend UI elements that interact with that endpoint to use the correct method (e.g. replacing an `<a>` tag with a `<form method="POST">`) and pass the CSRF token.
**Prevention:** When resolving backend vulnerabilities that change request methods, always search the codebase (including frontend templates) for references to the endpoint and update them accordingly. Write tests that cover the UI interaction flow.

## 2026-07-15 - [Enhancement] Security Headers and Session Cookie Flags
**Vulnerability:** The application was missing basic security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection) and secure session cookie flags (HttpOnly, SameSite).
**Learning:** Implementing security headers and secure cookie flags adds a layer of defense-in-depth against common web vulnerabilities like Clickjacking and XSS.
**Prevention:** By default, configure web frameworks to set these headers and cookie attributes, while being mindful of environment constraints (e.g., omitting Secure for local HTTP development).

## 2026-07-18 - [Fix] Inadequate Password and Username Length Validation
**Vulnerability:** The application was not enforcing length constraints on user inputs such as usernames and passwords. This allows attackers to send extremely long inputs that can either cause unexpected database errors (DataError on `String(80)`) or lead to a Denial of Service (DoS) attack by forcing the server to hash extremely long passwords, consuming disproportionate CPU time.
**Learning:** Application-layer boundary checks (e.g. Length validators) must be in place before processing expensive operations like password hashing or database commits, as relying on database limits will still waste CPU or trigger unhandled app exceptions.
**Prevention:** Always enforce strict length limits on inputs matching the database schema and security bounds, particularly for strings that are passed to expensive cryptographic hashing functions (like `werkzeug.security.generate_password_hash`).
## 2026-07-16 - [Fix] Application-Layer Boundary Checking for DoS and DataErrors
**Vulnerability:** The application was missing strict length validation on user inputs (username, password) before hitting the database or expensive hashing algorithms. Extremely long inputs could trigger unhandled database `DataError` exceptions or lead to Denial of Service (DoS) attacks via CPU exhaustion when hashing overly long passwords.
**Learning:** Application-layer boundary checking is crucial. Database schema constraints (like `VARCHAR(80)`) will cause fatal errors if breached, and algorithms like bcrypt scale non-linearly with input length.
**Prevention:** Always enforce explicit length constraints (e.g. using `Length(max=...)` validators in WTForms and `len() > max_len` checks in API routes) for usernames, passwords, and text fields to prevent DoS and DB crashes.

## 2024-08-04 - [Fix] Standardized Input Length Limits & Broken Checks
**Vulnerability:** Input fields lacked standardized boundary limits (e.g., descriptions allowing unlimited length) and multiple validation paths had duplicated, conflicting logic (like checking `len > 128` on one line and `len > 72` in another line). This caused both DoS potential (excessive parsing/hashing) and 500 crashes (Null values in APIs or DataErrors).
**Learning:** Security validations (like limiting description to 255 chars or passwords to 72 chars) must be applied uniformly across both UI (WTForms) and API logic. Validation logic must handle edge cases like `null` gracefully (e.g. `data.get('description') or ''`) to prevent 500 errors.
**Prevention:** Unify validation logic, write clear test cases for edge limits, and ensure all text fields entering the database explicitly map to the schema limits.

## 2024-08-11 - [Fix] Missing Login Rate Limiting
**Vulnerability:** The `/login` endpoints in both the web application (`app.py`) and the JSON API (`auth.py`) lacked rate limiting. This missing protection allows attackers to perform brute-force or credential stuffing attacks by making an unlimited number of login attempts, potentially compromising user accounts.
**Learning:** Authentication endpoints are prime targets for automated attacks. Without rate limiting, the application cannot effectively block rapid, repeated login attempts from a single source.
**Prevention:** Always implement rate limiting on sensitive endpoints, especially authentication endpoints like `/login`. Use an IP-based dictionary (or better, a caching solution like Redis for distributed setups) to track and restrict the number of requests per IP within a given time window.
