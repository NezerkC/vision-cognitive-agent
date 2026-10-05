# Vision OS

Local-first cognitive agent. A watchdog supervises 14 Python services that talk over a TCP event broker; a FastAPI
gateway serves the web HUD on `127.0.0.1:8000`; a LangGraph orchestrator routes each request through memory
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

4. Open <http://127.0.0.1:8000>. Service health is written every 3 s to `config/.health_status.json`; all 14 services
   should report `running`. Stop with `Ctrl+C`.

> The first start downloads the BGE-M3 embedding model (~2 GB) from Hugging Face; the gateway answers once it loads.

## Run modes

| Mode | Command | Behavior |
|------|---------|----------|
| Mock | `python core\main.py --mock` | Every service with a mock switch is simulated. Safe default for development. |
| Configured | `python core\main.py` | Per-service switches in `config/arranque.yaml` (`false` = real). |
| Desktop | `python start_all.py` | Backend plus Vision Studio dev (needs Node, Rust/cargo, MSVC build tools, WebView2; run `npm install` in `vision_studio/` once). |

> **Real mode has side effects.** With the current `config/arranque.yaml`, `ejecutor_izquierdo` controls mouse and
> keyboard and can run shell commands, `vision_parietal` captures the screen every 5 s, and `habla_parietal` speaks
> aloud. Switch them to `true` (mock) unless you want that.

## Services and ports

| Component | Where | Address |
|-----------|-------|---------|
| Event broker (JSON lines over TCP) | `core/broker_eventos.py` | `127.0.0.1:5000` |
| Gateway: REST, WebSocket `/ws`, web HUD | `sentidos/sistema_periferico.py`, `gui/` | `127.0.0.1:8000` |
| Vision Studio dev server | `vision_studio/` | `localhost:1420` |
| Ollama (default routing strategy `locales`) | external | `localhost:11434` |
| LM Studio / llama-server / ComfyUI | external, optional | `1234` / `8080` / `8188` |

The watchdog (`core/main.py`) starts the broker first, then the rest, restarts crashed services with backoff, and runs
every service from the project root with the project on `PYTHONPATH`.

## Configuration

| Variable | Used by |
|----------|---------|
| `OPENROUTER_API_KEY` | LLM router fallback when Ollama fails, notebook syntheses and chat |
| `TAVILY_API_KEY` | Web search and the curiosity protocol (`protocolo_intriga`) |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LMSTUDIO_API_KEY` | LiteLLM, when the active strategy uses those providers |

- `.env` is loaded by the watchdog for every service; variables already set in your shell take precedence.
- Keys saved from the HUD settings go to `.env` and apply to the other services on their next restart.
- `config/llm_router.yaml` picks the routing strategy and models; `api_key` accepts `${VAR}` or `VAR` references.
- `config/arranque.yaml` holds the mock switches; `config/memory_tiering.yaml` the hot/cold memory stores.

## Development

| Task | Command |
|------|---------|
| Dev tools (once) | `python -m pip install pytest pytest-asyncio pytest-cov ruff==0.15.22 pre-commit` |
| Tests (offline, ~15 s) | `python -m pytest tests` |
| Lint | `ruff check core/ cognitivo/ sentidos/ memoria/ tests/` |
| Format check | `ruff format --check core/ cognitivo/ sentidos/ memoria/ tests/` |
| Git hooks | `pre-commit install` |
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
- The broker accepts JSON-object lines only and drops any other connection, so web pages cannot inject events.
- `.env`, `memoria_activa/` and `archivo_profundo/` are git-ignored; never commit keys.

## Known limitations

- `ejecutor_izquierdo` runs shell commands chosen by the LLM without an allowlist or human approval step; keep it in
  mock unless you trust the prompts.
- The gateway loads BGE-M3 at import time, which slows the first start.
- The llama.cpp integration uses machine-specific paths (`sentidos/sistema_periferico.py`, `cognitivo/gestor_llamacpp.py`).
- The hexagonal refactor (`refactor/clean-hexagonal-architecture`: in-process event bus, ports and adapters, single
  runtime) is not merged yet.

## License

[MIT](LICENSE)
