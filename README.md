# Puffx AI Engine

A Python 3.11+ FastAPI gateway with an Ollama local inference adapter and an OpenAI-shaped chat endpoint. The `mock` provider is test-only. No model weights are included.

## Windows local setup

1. Install Python 3.11+ and Ollama using their official installers.
2. From the repository root run `installers\windows\install.bat`.
3. Copy `.env.example` to `.env`; set unique high-entropy `API_KEY` and `ADMIN_PASSWORD` values.
4. Download a model with `installers\windows\download_model.bat qwen2.5:3b` (check its license first).
5. Run `installers\windows\start.bat`; it binds to 127.0.0.1:8000. Stop with Ctrl+C.
6. Check `http://127.0.0.1:8000/health`. `model_available` must be true before inference.

Offline inference works after Ollama, the model, Python dependencies, and all runtime files are installed. The installer is a batch script, not a standalone executable. Python 3.11+ is intended; only Python 3.13 is available in the authoring environment, and dependency installation could not be verified there.

## Linux VPS and cPanel

See [VPS deployment](docs/vps.md), [cPanel modes](docs/cpanel.md), and [security guidance](docs/security.md). Compose publishes the API only on loopback. Put Nginx with TLS in front and firewall inference ports. Native cPanel inference depends on provider capabilities; use the remote gateway when the host cannot keep an inference runtime alive.

## API

- `GET /health`: unauthenticated live model discovery.
- `GET /v1/models` and `POST /v1/chat/completions`: `Authorization: Bearer <API_KEY>`.
- `GET /admin/usage`, `GET /admin/status`, `POST /admin/keys?label=...`, and `DELETE /admin/keys/{id}`: bearer `ADMIN_PASSWORD`.

Chat accepts system/user/assistant messages, temperature, max_tokens and stream. The current streaming compatibility mode buffers generation and sends one SSE content chunk. Embeddings are not implemented. JSON response formatting is not enforced by all backends. Usage token counts for Ollama currently report zero because that adapter does not map runtime token metrics.

Example requests and PHP, Python and JavaScript clients are under `examples/`. Keep API credentials on trusted server-side systems.

## Configuration and model licenses

Copy `.env.example` to `.env`; never commit the file. SQLite is implemented; PostgreSQL is not wired despite being a possible future option. `MODEL_PATH` is reserved; Ollama manages its own model store. Pull compatible models from legitimate sources and review each model's license and use restrictions. `qwen2.5:3b` is an example, not a bundled or endorsed weight. Resource needs vary with quantization and context size.

## Validation

Install requirements with `python -m pip install -r requirements.txt`, then run `pytest -q`. Tests use mocked inference. A real inference check additionally needs Ollama and a locally available model. The authoring environment had Python 3.13 but a broken pip installation and no pytest, so automated tests could not run here; `compileall` passed.

