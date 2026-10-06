# Vision OS

Local-first cognitive agent. An orchestrator runs the cognitive, sensory and memory services on a shared event bus
(in one process by default, or as supervised processes); a FastAPI gateway serves the web HUD on `127.0.0.1:8000`;
a LangGraph orchestrator routes each request through memory
(LanceDB), web search and LLMs (LiteLLM: Ollama, OpenRouter, LM Studio, ...). Vision Studio (Tauri + React) is an
optional desktop IDE on top of the same gateway.

## Quick start (Windows, PowerShell)

1. Create the environment (Python 3.11+):

   ```powershell
   py -3.11 -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

2. Configure keys (optional in mock mode):

   ```powershell
   Copy-Item .env.example .env   # then fill in the keys you have
   ```

3. Start everything in mock mode (no LLM calls, no screen, microphone, speech or keyboard control):

   ```powershell
   python core\main.py --mock
   ```

4. Open <http://127.0.0.1:8000>. The console logs `Iniciando servicio...` once per service; a service that crashes is
   restarted after 3 s. Stop with `Ctrl+C`.

> The first start downloads the BGE-M3 embedding model (~2 GB) from Hugging Face in the background; the gateway
> answers right away and notebooks become available once the model is loaded.

## Run modes

| Mode | Command | Behavior |
|------|---------|----------|
| Mock | `python core\main.py --mock` | Every service with a mock switch is simulated. Safe default for development. |
| Configured | `python core\main.py` | Per-service switches in `config/arranque.yaml` (`false` = real). |
| Multi-process | `python core\main.py --mock --multi-process` | Same services as separate supervised processes (health in `config/.health_status.json`). Combine with or without `--mock`. |
| Desktop | `python start_all.py` | Backend plus Vision Studio dev (needs Node, Rust/cargo, MSVC build tools, WebView2; run `npm install` in `vision_studio/` once). |

> **Real mode has side effects.** With the current `config/arranque.yaml`, `ejecutor_izquierdo` controls mouse and
> keyboard and can run shell commands (each action only after you approve its ticket in the HUD), `vision_parietal`
> captures the screen every 5 s, and `habla_parietal` speaks aloud. Switch them to `true` (mock) unless you want that.

## Services and ports

| Component | Where | Address |
|-----------|-------|---------|
| Event bus TCP endpoint (JSON lines) | `core/adapters/event_bus_tcp_bridge.py` (default), `core/broker_eventos.py` (`--multi-process`) | `127.0.0.1:5000` |
| Gateway: REST, WebSocket `/ws`, web HUD | `sentidos/sistema_periferico.py`, `gui/` | `127.0.0.1:8000` |
| Vision Studio dev server | `vision_studio/` | `localhost:1420` |
| Ollama (default routing strategy `locales`) | external | `localhost:11434` |
| LM Studio / llama-server / ComfyUI | external, optional | `1234` / `8080` / `8188` |

By default `core/main.py` runs `core/orchestrator.py`: every service as a supervised task in one process, on an
in-memory event bus (`core/adapters/event_bus_inmemory.py`) exposed on port 5000 by a TCP bridge. With
`--multi-process` the watchdog starts the TCP broker and each service as a separate process instead. Either way the
services run from the project root with `.env` loaded.

The core follows a hexagonal layout: domain entities in `core/domain/`, ports (`typing.Protocol`) in `core/ports/`,
implementations in `core/adapters/`.

## Configuration

| Variable | Used by |
|----------|---------|
| `OPENROUTER_API_KEY` | LLM router fallback when Ollama fails, notebook syntheses and chat |
| `TAVILY_API_KEY` | Web search and the curiosity protocol (`protocolo_intriga`) |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LMSTUDIO_API_KEY` | LiteLLM, when the active strategy uses those providers |
| `VISION_MAX_UPLOAD_BYTES` | Gateway upload limit in bytes (default 52428800, 50 MB); larger uploads get HTTP 413 |

- `.env` is loaded by the watchdog for every service; variables already set in your shell take precedence.
- Keys saved from the HUD settings go to `.env` and apply to the other services on their next restart.
- `config/llm_router.yaml` picks the routing strategy and models; `api_key` accepts `${VAR}` or `VAR` references.
- Embeddings come from BGE-M3 (downloaded from Hugging Face on first use). If it cannot load, the memory service
  stops with an explicit error instead of falling back to fake vectors. Each vector store records its embedder in
  `embedder.json` and refuses vectors from another one; after upgrading, or after switching embedders, run
  `python -m memoria.reindex` once to recompute the stored vectors from their text.
- `config/arranque.yaml` holds the mock switches. Every service runs for real unless its flag is `true` or `--mock`
  is passed; a missing key means real mode. `config/memory_tiering.yaml` holds the hot/cold memory stores.

## Development

| Task | Command |
|------|---------|
| Dev tools (once) | `python -m pip install pytest pytest-asyncio pytest-cov ruff==0.15.22 pre-commit` |
| Tests (offline, ~15 s) | `python -m pytest tests` |
| Lint (whole repo, like CI) | `ruff check .` |
| Format check | `ruff format --check .` |
| Git hooks | `pre-commit install` |
| Studio unit tests | `cd vision_studio; npm test` |
| Studio type-check and build | `cd vision_studio; npm run build` |

- Ruff is pinned to `0.15.22` (CI, pre-commit and dev deps). Without installing it: `uvx ruff@0.15.22 check ...`.
- Workflow rules (branches from `develop`, Conventional Commits, mandatory tests and lint) live in
  [`.agents/AGENTS.md`](.agents/AGENTS.md). CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs a secret
  scan, ruff and pytest on Python 3.11 and 3.12.
- Plans, specs and audits go in `material_complementario/`.

## Project layout

Folders are named after the brain region each part plays:

| Folder | Contents |
|--------|----------|
| `core/` | Watchdog, event broker, Amygdala (prompt safety), event schemas |
| `cognitivo/` | LLM router, LangGraph orchestrator, executor, notebooks (RAG), web search |
| `sentidos/` | Gateway (FastAPI), vision, hearing, speech, image generation, local security guards |
| `memoria/` | LanceDB hot/cold vector memory, hippocampus consolidation |
| `gui/` | Web HUD served by the gateway |
| `vision_studio/` | Tauri + React desktop IDE |
| `config/` | Runtime configuration |
| `tests/unit/` | Pytest suite |

## Security model

- The gateway serves only local origins: CORS allowlist, cross-site write rejection and a WebSocket origin check
  (`sentidos/seguridad_local.py`). Credentials are returned masked and only known provider keys can be written.
- The event bus TCP endpoint (bridge or broker) accepts JSON-object lines only and drops any other connection, so web
  pages cannot inject events.
- Uploads are read in chunks and rejected with 413 above `VISION_MAX_UPLOAD_BYTES`. Notebook ids are checked against
  the notebook metadata before any file is written, so a crafted id cannot write outside the notebook's folder.
- The file tree and file search only cover the folder opened through `/api/workspace/open` (filesystem roots are
  refused, invalid paths return 404 instead of falling back to the repository). `clone_git` accepts only https/ssh
  remotes and passes them after `--`, so a URL cannot smuggle git options.
- Vision Studio's Rust commands only touch the workspace registered through `set_workspace`: paths are canonicalized
  and must stay inside it, reads are capped at 10 MB, and every PowerShell command needs confirmation in a native
  dialog that script in the webview cannot skip. Each command is granted explicitly in
  `vision_studio/src-tauri/capabilities/default.json`, and the app ships a Content Security Policy.
- Auto-training never writes code into the package: tool code the LLM writes for a detected CLI is kept only if it
  parses and defines a `@tool` function, and it goes to `memoria_activa/skills_propuestas/<cli>_tool.py.txt` for a
  human to review before moving it into `cognitivo/skills/`.
- `ejecutor_izquierdo` runs nothing on its own: every keyboard/mouse or shell action waits for an approve/reject ticket
  in the HUD (`canal.ejecucion.aprobacion`). Pending requests expire after 5 minutes and can be decided only once.
- `.env`, `memoria_activa/` and `archivo_profundo/` are git-ignored; never commit keys.

## Known limitations

- Approved shell commands run with your user's permissions; there is no allowlist beyond your own review.
- The llama.cpp integration uses machine-specific paths (`sentidos/sistema_periferico.py`, `cognitivo/gestor_llamacpp.py`).
- The hexagonal migration is partial: there is no application (use case) layer yet, only the event bus ports have
  adapters, and the gateway still calls LanceDB and the notebooks manager directly.
- Events carry only `topic` and `data` (no id, type, timestamp or trace context), consumers are not idempotent in
  general, and there is no dead-letter queue.

## License

[MIT](LICENSE)
