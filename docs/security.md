# Security notes

Use HTTPS at a reverse proxy for public deployments. Generate unique high-entropy API/admin passwords and protect the environment file. API keys created through the admin endpoint are returned once and stored as SHA-256 digests; revoke by key ID. Restrict dashboard access to trusted administrators. Current admin authentication uses a bearer password, so use a long unique secret and TLS. The built-in rate limiter is process-local and IP-based; it is not a distributed quota system. Do not expose Ollama port 11434 publicly. Browser and mobile apps must not embed server secrets.
