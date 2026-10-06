# Production Readiness Plan

Goal: make Vision OS and Vision Studio fully functional with no fake behavior in production code paths.
Source: read-only audits of 2026-10-06 (backend mocks, notebooks/RAG, Vision Studio file manager).

This file is the single source of truth for the work loop. Each loop iteration completes ONE task.

## Environment

- Worktree: `D:/projects/02_Proyectos_Dev/vision-cognitive-agent/.claude/worktrees/production-readiness`
- Python: `D:/projects/02_Proyectos_Dev/vision-cognitive-agent/.venv/Scripts/python.exe` (run it from the worktree root so the worktree code is imported)
- Frontend: `vision_studio/` (run `npm ci` once in the worktree before the first frontend task)
- Branches are chained; each phase branches from the previous phase branch:

| Phase | Branch | PR base |
|---|---|---|
| 0 | `fix/security-hardening` | `main` |
| 1 | `fix/remove-production-mocks` | `fix/security-hardening` |
| 2 | `feat/notebooks-production` | `fix/remove-production-mocks` |
| 3 | `feat/studio-file-manager` | `feat/notebooks-production` |
| 4 | `feat/imagination-dreams` | `feat/studio-file-manager` |

## Rules

1. Strict TDD: write a failing test in `tests/unit/` first, make it pass, then refactor.
2. Mocks and fakes are allowed in tests only. Production code must never return simulated data. When a dependency is missing, it raises or returns an explicit error.
3. Before every commit, all of these must pass: `ruff check .`, `ruff format --check .`, `pytest -q tests/unit -p no:cacheprovider`. Frontend tasks also need `npm test` and `npm run build` in `vision_studio/`. Rust tasks also need `cargo check`.
4. Use conventional commits. No `Co-Authored-By`, no AI attribution. Commit the plan update (checkbox + log line) together with the task.
5. Push with `git push -u origin <branch>`.
6. Never: merge PRs, push to `main`, force-push, use `--no-verify`, delete data outside the repository, weaken security checks, download files larger than 100 MB, or add credentials.
7. If a task needs a human (a decision, a credential, a large model download, hardware validation), mark it `[!]`, record the reason under Blockers, and continue with the next task.
8. When every task in a phase is `[x]` or `[!]`: push, open the phase PR (not draft) with `gh pr create --base <PR base>`, record the URL under Log, and create the next phase branch from the current one.
9. When every phase is finished: write a final summary under Log and stop the loop.

## Defaulted decisions

- Filesystem backend for the file manager: Rust/Tauri commands scoped to the opened workspace.
- Missing `modos_mock` keys mean real mode.
- Embeddings: fail hard when the configured model cannot load. Store the embedder id and dimension so mixed vector spaces are rejected.
- All notebook LLM calls go through `LLMRouter`.

## Phase 0: Security

- [x] 0.1 Notebook path traversal: validate that the notebook exists and that `notebook_id` is a safe id before any filesystem write in `chat_cuaderno_stream` (`cognitivo/cuadernos_manager.py` ~426-442).
- [x] 0.2 Upload size limit on the notebook upload endpoint (`sentidos/sistema_periferico.py` ~1312-1319). Configurable, default 50 MB, respond 413.
- [x] 0.3 File tree and `/api/archivos` endpoints: restrict them to the opened workspace and return an error for invalid paths instead of falling back to `PROJECT_ROOT` (`sentidos/sistema_periferico.py` ~1051-1086, ~1368-1396).
- [x] 0.4 Tauri commands: scope `read_file_content` and `write_file_content` to the active workspace (canonicalize, reject paths outside it, cap file size). Remove the arbitrary PowerShell command or gate it behind an allowlist plus explicit approval (`vision_studio/src-tauri/src/lib.rs` 19-62). Add an app-command permission manifest (`build.rs`) and a strict CSP (`tauri.conf.json`).
- [x] 0.5 The AI chat `read_file` and `write_file` tools require user approval (`vision_studio/src/components/Sidebar/SidebarChat.tsx` ~291-316). `execute_powershell` already gets a native confirmation in Rust since 0.4, so drop its duplicate in-app prompt.
- [x] 0.6 Protocolo de Intriga must never write generated code into the package (`cognitivo/protocolo_intriga.py` ~161-181). Delete the generated junk files `cognitivo/skills/{cargo,docker,gcloud,git,go,kubectl,npm,pip,python}_tool.py` after confirming nothing imports them.

## Phase 1: Remove production mocks

- [x] 1.1 Missing `modos_mock` keys mean real mode (`core/orchestrator.py:84`, `core/main.py:106`, daemon reload code in `sentidos/oido_parietal.py:212`, `sentidos/habla_parietal.py:220`, `sentidos/vision_parietal.py:204`, `cognitivo/ejecutor_izquierdo.py:270`). Set every `config/arranque.yaml` mock flag to false.
- [x] 1.2 Embeddings: remove the MD5/SHA fallbacks in `memoria/lancedb_manager.py` (55-94). Raise a clear error when the model cannot load. Record embedder id and dimension.
- [x] 1.3 `cognitivo/llm_router.py`: errors raise and publish a failed status (351, 394-396). Remove the `mock: true` canned answers (124-128; `cognitivo/orquestador_graph.py` 118-124, 165-169, 219-238, 300-301).
- [x] 1.4 `cognitivo/llm_router.py`: forward `image_base64` as a multimodal message to the model set in `modelo_vision` (179-186, 316-327).
- [x] 1.5 Protocolo de Intriga: remove the fake-solution fallback (35-43, 60-65). Implement or remove the transcription approval flow (151-155, `gui/app.js` 364-378).
- [x] 1.6 Ejecutor: simulated UI and shell actions return an error, not success (`cognitivo/ejecutor_izquierdo.py` 88-90, 120-122).
- [x] 1.7 Senses: a vision capture error publishes an error instead of a blue image, and `mss` re-initializes on reload (`sentidos/vision_parietal.py` 57-63, 204-205, 230-232). Oido and Habla fail loudly when dependencies are missing. A failed transcription does not save a placeholder (`sentidos/sistema_periferico.py` 836-841). `sentidos/calibrador_audio.py` drops the random RMS values.
- [x] 1.8 Telemetry: real NVML or `nvidia-smi` values, or null. No hardcoded GPU name or temperatures (`sentidos/sistema_periferico.py:1241`, `gestor_llamacpp.py` 144-147, 174).
- [x] 1.9 Pineal daemon: summarize real activity through `LLMRouter` instead of fixed text (`daemons/pineal_daemon.py` 103-106). Consolidation moves rows instead of duplicating them (65-96).
- [x] 1.10 `/api/memoria` uses the real schema columns (`sentidos/sistema_periferico.py` 386-392). Remove the hardcoded sample nodes in `gui/app.js` (1092-1101). Fix the `temperatura_z` schema mismatch in `memoria/cargador_datasets.py` (84, 90).
- [ ] 1.11 `cognitivo/memoria.py` propagates save errors (92-97). `/api/health` works in in-process mode (`sentidos/sistema_periferico.py` 293-298).
- [ ] 1.12 Move `core/test_*.py` to `tests/integration/` (skipped without a running broker) or delete the ones already covered by unit tests.
- [ ] 1.13 Topics without a production producer: wire them or remove their consumers (`canal.imaginacion.peticion`, `canal.web.busqueda`, `canal.sistema.fin_tarea`, `canal.ejecucion.accion`, `canal.sensorial.audio.hablar`). Forward voice transcriptions to `canal.cognitivo.entrada`.

## Phase 2: Notebooks (NotebookLM) and RAG agent

- [ ] 2.1 Remove the notebook fakes: raw-chunk chat answer (`cognitivo/cuadernos_manager.py` 527-529), raw-context synthesis note (376-378), deep-report template (453-463), placeholder auto-research source (293-294). An empty notebook returns an error.
- [ ] 2.2 Route notebook LLM calls through `LLMRouter` (366-367, 513-514).
- [ ] 2.3 Ingestion: stop running `clean_web_text` on files and keep newlines (36-39, 215). Add DOCX via `python-docx`. Reject unsupported types. Replace chunks when a source is re-uploaded.
- [ ] 2.4 New source types: URL (fetch and extract the main content), YouTube transcript, pasted text.
- [ ] 2.5 Add a `source_id` column to chunks. Endpoints and UI to delete a source, toggle sources per query and view source content.
- [ ] 2.6 Run embedding off the event loop (`asyncio.to_thread`) and in batches. Recover sources stuck in `processing` on startup.
- [ ] 2.7 Hybrid retrieval for `cuadernos_chunks`: FTS index plus RRF, reusing the logic in `memoria/lancedb_manager.py`.
- [ ] 2.8 Structured citations (`source_id`, `chunk_index`), clickable in the UI. Render chat and notes as Markdown.
- [ ] 2.9 Rename notebooks, delete notes, persist chat history.
- [ ] 2.10 Notes cover the whole notebook (map-reduce over all chunks). Add briefing and mind map. Podcast audio via edge-tts.
- [ ] 2.11 Deep search: fetch full pages, store one source per URL, have the LLM write the report, let the user choose which sources to keep. Replace the `max_web_results > 10` mode hack with an explicit parameter.
- [ ] 2.12 Agent: add a `nodo_cuadernos` station to `cognitivo/orquestador_graph.py` that calls `CuadernosManager.query_cuaderno_context`, injected through `config["configurable"]`. Add the active `notebook_id` to `EstadoAgente`.
- [ ] 2.13 Notebooks UI: real drag and drop, surface upload errors, read the API base URL from settings instead of hardcoding `http://127.0.0.1:8000`.

## Phase 3: Vision Studio file manager

- [ ] 3.1 Rust `list_dir` command: lazy, folders first, ignore `.git` and `node_modules`, show other dotfiles, entry cap, scoped to the workspace.
- [ ] 3.2 Native folder dialog with `tauri-plugin-dialog`. Remove the hardcoded recent-project path.
- [ ] 3.3 Open a file into Monaco: open-files store, language from extension, binary and large-file detection.
- [ ] 3.4 Ctrl+S saves. Dirty indicator, multiple tabs, close with an unsaved-changes prompt. Real Ln/Col and language in the status bar.
- [ ] 3.5 Create, rename, move, and delete to the recycle bin (`trash` crate) with confirmation, from a context menu.
- [ ] 3.6 Watch external changes with the `notify` crate and refresh the tree from emitted events.
- [ ] 3.7 Search in file contents, scoped to the workspace.
- [ ] 3.8 Bundle Monaco locally (`loader.config({ monaco })`) so it works offline, then remove `https://cdn.jsdelivr.net` from the CSP in `tauri.conf.json`.
- [ ] 3.9 Real PTY terminal (`portable-pty`) wired to xterm `onData` and resize.
- [ ] 3.10 Git panel shows real `git status`, or is removed. Remove the hardcoded extensions list.

## Phase 4: Imagination and dreams

- [ ] 4.1 `IImageGenerator` port in `core/ports/`.
- [ ] 4.2 ComfyUI adapter: queue with `POST /prompt`, wait through `/history`, download through `/view`. Configurable workflow and checkpoint. Raise when ComfyUI is unreachable.
- [ ] 4.3 Google image adapter (Gemini API) behind a config key. Raise when the key is missing.
- [ ] 4.4 Local-first routing between image adapters.
- [ ] 4.5 Producer for `canal.imaginacion.peticion` (a chat command and a tool in the agent graph).
- [ ] 4.6 Dream cycle in the pineal daemon: unload the local LLM, generate from high-W memories, store results in memory.

## Blockers

- Human step after merging phase 1: run `python -m memoria.reindex` in the main checkout. Its memory stores have no embedder record, likely hold hash vectors, and older unit tests wrote test rows into the real `memoria_activa`.

## Log

(one line per completed task: `<task id> <summary>`; the task's commit is the one that adds the line)

- 0.1 Notebook ids are validated against metadata and confined to `SOURCES_DIR` before any filesystem write; unknown notebooks return 404 from the chat, upload and delete endpoints.
- 0.2 Gateway uploads (notebook sources, `/api/memoria/aprender`, `/upload_sensorial`) are read in chunks and rejected with 413 above `VISION_MAX_UPLOAD_BYTES` (default 50 MB).
- 0.3 New `/api/workspace/open` sets the active workspace; tree and file search stay inside it (403 outside, 404 for missing paths, no fallback to the repo). `clone_git` only accepts https/ssh URLs passed after `--`. Vision Studio's FileTree opens the folder and shows gateway errors.
- 0.4 Rust `set_workspace` state; `read_file_content`/`write_file_content` canonicalize paths and stay inside the workspace (reads capped at 10 MB); `execute_powershell_command` runs inside the workspace only after a native confirmation dialog; app-command permission manifest plus explicit grants; CSP (verified with no violations against the built frontend).
- 0.5 Chat tool access goes through `decideToolAccess` (Vitest-covered): reads and writes ask for approval unless the level is autonomous, read-only denies writes and PowerShell, PowerShell relies on the native Rust confirmation, unknown tools are denied. Vision Studio now has a Vitest `npm test` script.
- 0.6 Auto-training quarantines LLM-written tool code in `memoria_activa/skills_propuestas/*.py.txt` (validated CLI name, must parse and define a `@tool` function) instead of writing into `cognitivo/skills`; the CLI scan skips CLIs with a pending proposal; the 9 generated mock skill files are deleted.
- Phase 0 PR: https://github.com/NezerkC/vision-cognitive-agent/pull/2
- 1.1 `core/arranque.py` is the single reader of `config/arranque.yaml`: a missing file or key means real mode. The orchestrator, watchdog, daemon reloads and the gateway defaults use it, and the shipped config runs every service for real.
- 1.2 Embedder failures raise `EmbedderUnavailableError` (no hash/SHA fallback); explicit mock vectors are tagged `mock-hash`; every store records its embedder in `embedder.json` and refuses mismatches; `python -m memoria.reindex` re-embeds stored text; memory tests no longer write into the real `memoria_activa`.
- 1.3 The LLM path has no mock mode: canned answers are gone from `call_llm` and the graph nodes; `enrutar_peticion` and the graph raise instead of returning error text, so `process_request` publishes `status: failed` with the error.
- 1.4 Requests with `image_base64` go to the vision model from `hardware_interfaces.json` as a multimodal message (`cognitivo/modelo_vision.py`, `local/` = Ollama) instead of the text graph, which never saw the image; the gateway's image learning uses the same model; a missing model is an error.
- 1.5 Intriga searches through the shared `WebSearchEngine` and returns nothing instead of a simulated solution; nothing is saved when the search finds nothing; anomalies now ask for permission (the existing HUD ticket and spoken si/no answers work) before any research; auto-training stops when no documentation is found.
- 1.6 The executor reports `error` (never success or exit code 0) for actions it did not run: mock mode, missing pyautogui (with the import error), and batches with unknown UI commands, which are now rejected before any key is pressed.
- 1.7 Vision raises `ScreenCaptureError` instead of falling back to mock or a blue frame, announces each distinct capture error once, and creates `mss` lazily (so mock to real reloads work). Hearing and speech report missing packages or models (`unavailable_reason`, HUD announcement) instead of idling as mock. A failed audio transcription returns an error and saves nothing. The audio calibrator exits with 1 instead of showing random levels.
- 1.8 GPU name, VRAM and temperatures come from `nvidia-smi` and psutil sensors or are `null` (no 16 GB / 45 °C / 50 °C placeholders); the gateway reports the detected GPU name. Vision Studio reads the gateway's camelCase telemetry (the status bar never matched it and always showed a fixed 28.5 %), drops the persisted fake `systemTelemetry`, and shows a dash for missing readings.
- 1.9 The pineal daemon records screen context, voice and requests between sleeps and asks the LLM to summarize them; no activity or an LLM failure stores nothing (activity is kept for the next cycle). Consolidation moves decayed hot rows to the cold tier (copy, then delete) instead of copying them every cycle. Sleep now needs 10 minutes of idle instead of 10 seconds.
- 1.10 `/api/memoria` reads the real columns with `table_names()` (it used non-existent columns and `list_tables()`, so it returned nothing or zeros) and returns W and metadata; the web HUD shows an empty graph instead of sample nodes. The dataset loader and the learning endpoint save through the memory schema (`temperatura_z` made every dataset save fail). `handle_guardar` returns whether it saved, and an empty cold table no longer silently redirects cold memories to the hot tier.
