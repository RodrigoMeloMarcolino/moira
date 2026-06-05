# ADR 0012 - Provider signup password policy

## Status

Accepted

## Context

Provider signup creates the authenticated user account used by a provider to
access the platform. Password length is therefore a functional signup rule, not
only an implementation detail of the password hashing library.

NIST SP 800-63B requires subscriber-chosen memorized secrets to be at least 8
characters and recommends supporting at least 64 characters. OWASP's Password
Storage Cheat Sheet notes that bcrypt has a practical input limit of 72 bytes in
most implementations.

Moira currently uses bcrypt directly for password hashing.

## Decision

For the MVP, provider signup passwords must be between 8 and 64 characters.

The signup API accepts the raw password only in the request body. The password
must never be returned by the API. The backend persists only a bcrypt hash in
`users.password_hash`.

## Consequences

- The password policy is explicit in the auth domain and reused by signup
  validation.
- The Pydantic signup schema rejects passwords outside the functional range with
  `422 Unprocessable Entity`.
- The signup use case also validates the password policy before hashing, so the
  rule is protected outside FastAPI.
- The 64-character maximum supports long passphrases and stays below bcrypt's
  72-byte practical limit for common ASCII passwords.
- If Moira later needs strict support for longer Unicode passphrases, the policy
  can evolve to validate UTF-8 byte length or migrate to a hashing algorithm
  such as Argon2.

## References

- NIST SP 800-63B
- OWASP Password Storage Cheat Sheet
