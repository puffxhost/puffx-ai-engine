# cPanel deployment

## Native inference (conditional)

Use cPanel Setup Python App only if the host provides Python 3.11+, a supported persistent application runner, writable storage, sufficient memory/disk/CPU, and permission for required packages and model runtime. Create an app, install requirements, set environment variables and Passenger entry point (`passenger_wsgi.py`). Shared cPanel commonly terminates long jobs or forbids local daemons/compilation; this repository cannot override host limits. If Ollama or a permitted compatible runtime cannot run persistently, native inference is unavailable. Do not assume Docker, shell, or daemons.

## Gateway/proxy

Set `INFERENCE_BACKEND=remote`, `REMOTE_INFERENCE_URL=https://reachable-ai-host`, and `REMOTE_API_KEY` in server-side environment settings. The gateway forwards requests from the server; upstream must be reachable from cPanel. Protect both endpoints with HTTPS and keys. A Windows computer behind NAT is not publicly reachable by default; use a VPN/private overlay or authenticated outbound tunnel instead of exposing a local inference port. Streaming is currently buffered by upstream adapter and emitted as one SSE chunk.
