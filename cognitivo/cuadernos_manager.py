import asyncio
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime
from typing import AsyncGenerator

import lancedb
import pyarrow as pa
from langchain_community.document_loaders import CSVLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from memoria.lancedb_manager import BGEM3Embedder, check_embedder_compatibility, sql_string_literal

logger = logging.getLogger("CuadernosManager")
logger.setLevel(logging.INFO)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUADERNOS_DIR = os.path.join(PROJECT_ROOT, "memoria_activa", "cuadernos")
METADATA_FILE = os.path.join(CUADERNOS_DIR, "notebooks.json")
SOURCES_DIR = os.path.join(CUADERNOS_DIR, "sources")
LANCE_DB_PATH = os.path.join(CUADERNOS_DIR, "lancedb_cuadernos")

os.makedirs(CUADERNOS_DIR, exist_ok=True)
os.makedirs(SOURCES_DIR, exist_ok=True)


def clean_web_text(text: str) -> str:
    """Sanitize and clean web text by removing HTML tags and excessive whitespace."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"function\s*\([^\)]*\)\s*\{[^\}]*\}", " ", clean)
    clean = re.sub(r"style=[^\s]+", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


class NotebookNotFoundError(ValueError):
    """The notebook id does not name an existing notebook."""


class EmptyNotebookError(ValueError):
    """The notebook has no indexed content to answer from or summarize."""


class NotebookLLMError(RuntimeError):
    """The language model failed to write a notebook answer, note or report."""


class WebSearchError(RuntimeError):
    """A web search requested for a notebook found nothing usable."""


EMPTY_NOTEBOOK_MESSAGE = (
    "El cuaderno no tiene fuentes indexadas. Agregá una fuente (o esperá a que termine de procesarse) "
    "antes de preguntar o generar notas."
)


def _notebook_sources_dir(notebook_id: str, metadata: dict[str, dict]) -> str:
    """Source directory of an existing notebook. Never resolves outside SOURCES_DIR."""
    if notebook_id not in metadata:
        raise NotebookNotFoundError(f"Cuaderno {notebook_id} no existe.")
    root = os.path.realpath(SOURCES_DIR)
    path = os.path.realpath(os.path.join(root, notebook_id))
    if os.path.dirname(path) != root:
        raise NotebookNotFoundError(f"Cuaderno {notebook_id} no existe.")
    return path


class CuadernosManager:
    def __init__(self):
        self.embedder = BGEM3Embedder(force_mock=False)
        self.db = lancedb.connect(LANCE_DB_PATH)
        self._ensure_lancedb_table()

    def _ensure_lancedb_table(self):
        schema = pa.schema(
            [
                ("vector", pa.list_(pa.float32(), self.embedder.dimension)),
                ("text", pa.string()),
                ("notebook_id", pa.string()),
                ("source_name", pa.string()),
                ("chunk_index", pa.int32()),
            ]
        )
        if "cuadernos_chunks" not in self.db.table_names():
            self.table = self.db.create_table("cuadernos_chunks", schema=schema)
            logger.info("LanceDB table 'cuadernos_chunks' created successfully.")
        else:
            self.table = self.db.open_table("cuadernos_chunks")
        check_embedder_compatibility(LANCE_DB_PATH, self.embedder, has_rows=self.table.count_rows() > 0)

    def _load_metadata(self) -> dict[str, dict]:
        if not os.path.exists(METADATA_FILE):
            return {}
        for attempt in range(3):
            try:
                with open(METADATA_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Error loading notebooks metadata: {e}")
                import time

                time.sleep(0.05)
        return {}

    def _save_metadata(self, metadata: dict[str, dict]):
        try:
            tmp_file = f"{METADATA_FILE}.tmp.{os.getpid()}_{uuid.uuid4().hex[:4]}"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, METADATA_FILE)
        except Exception as e:
            logger.error(f"Error saving notebooks metadata: {e}")

    def list_cuadernos(self) -> list[dict]:
        data = self._load_metadata()
        result = []
        for n_id, info in data.items():
            result.append(
                {
                    "id": n_id,
                    "title": info.get("title", "Sin título"),
                    "description": info.get("description", ""),
                    "created_at": info.get("created_at", ""),
                    "sources_count": len(info.get("sources", [])),
                    "notes_count": len(info.get("notes", [])),
                    "sources": info.get("sources", []),
                    "notes": info.get("notes", []),
                    "research": info.get("research"),
                }
            )
        return sorted(result, key=lambda x: x["created_at"], reverse=True)

    def create_cuaderno(self, title: str, description: str = "") -> dict:
        metadata = self._load_metadata()
        n_id = str(uuid.uuid4())[:8]
        new_notebook = {
            "id": n_id,
            "title": title,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "sources": [],
            "notes": [],
        }
        metadata[n_id] = new_notebook
        self._save_metadata(metadata)
        logger.info(f"Cuaderno creado: '{title}' ({n_id})")
        return new_notebook

    def ensure_cuaderno(self, notebook_id: str) -> None:
        """Raise NotebookNotFoundError unless notebook_id names an existing notebook."""
        _notebook_sources_dir(notebook_id, self._load_metadata())

    def delete_cuaderno(self, notebook_id: str) -> bool:
        metadata = self._load_metadata()
        if notebook_id not in metadata:
            return False
        n_sources_dir = _notebook_sources_dir(notebook_id, metadata)

        del metadata[notebook_id]
        self._save_metadata(metadata)

        # Delete LanceDB chunks for this notebook
        try:
            self.table.delete(f"notebook_id = {sql_string_literal(notebook_id)}")
        except Exception as e:
            logger.warning(f"Failed to delete LanceDB chunks for notebook {notebook_id}: {e}")

        # Delete source files
        if os.path.exists(n_sources_dir):
            import shutil

            shutil.rmtree(n_sources_dir, ignore_errors=True)

        logger.info(f"Cuaderno eliminado: {notebook_id}")
        return True

    async def add_fuente(
        self,
        notebook_id: str,
        filename: str,
        file_content: bytes,
        description: str | None = None,
        index_in_background: bool = True,
    ) -> dict:
        metadata = self._load_metadata()
        n_sources_dir = _notebook_sources_dir(notebook_id, metadata)

        # Uploaded names are untrusted: keep only the base name so writes stay inside the notebook dir.
        filename = os.path.basename(filename.replace("\\", "/"))
        if filename in ("", ".", ".."):
            raise ValueError("Nombre de archivo inválido.")

        os.makedirs(n_sources_dir, exist_ok=True)
        file_path = os.path.join(n_sources_dir, filename)

        with open(file_path, "wb") as f:
            f.write(file_content)

        source_id = str(uuid.uuid4())[:8]
        source_entry = {
            "id": source_id,
            "filename": filename,
            "description": description or "",
            "added_at": datetime.now().isoformat(),
            "status": "processing",
            "chunks": 0,
        }
        metadata[notebook_id]["sources"].append(source_entry)
        self._save_metadata(metadata)

        if index_in_background:
            asyncio.create_task(self._process_and_index_source(notebook_id, source_id, filename, file_path))
        else:
            await self._process_and_index_source(notebook_id, source_id, filename, file_path)

        return source_entry

    async def _process_and_index_source(self, notebook_id: str, source_id: str, filename: str, file_path: str):
        try:
            suffix = os.path.splitext(filename)[1].lower()
            text_content = ""

            if suffix == ".pdf":
                loader = PyPDFLoader(file_path)
                docs = await asyncio.to_thread(loader.load)
                text_content = "\n\n".join([d.page_content for d in docs])
            elif suffix == ".csv":
                loader = CSVLoader(file_path)
                docs = await asyncio.to_thread(loader.load)
                text_content = "\n".join([d.page_content for d in docs])
            else:
                try:
                    loader = TextLoader(file_path, encoding="utf-8")
                    docs = await asyncio.to_thread(loader.load)
                    text_content = "\n".join([d.page_content for d in docs])
                except Exception:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        text_content = f.read()

            if not text_content.strip():
                raise ValueError("No se pudo extraer contenido de texto del archivo.")

            text_content = clean_web_text(text_content)
            splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
            chunks = splitter.split_text(text_content)

            rows = []
            for idx, chunk_text in enumerate(chunks):
                vec = self.embedder.embed_query(chunk_text)
                rows.append(
                    {
                        "vector": vec,
                        "text": chunk_text,
                        "notebook_id": notebook_id,
                        "source_name": filename,
                        "chunk_index": idx,
                    }
                )

            if rows:
                await asyncio.to_thread(self.table.add, rows)

            # Update metadata status to ready
            metadata = self._load_metadata()
            if notebook_id in metadata:
                for src in metadata[notebook_id]["sources"]:
                    if src["id"] == source_id:
                        src["status"] = "ready"
                        src["chunks"] = len(rows)
                        break
                self._save_metadata(metadata)

            logger.info(
                f"Fuente '{filename}' procesada exitosamente ({len(rows)} chunks) para el cuaderno {notebook_id}."
            )

        except Exception as e:
            logger.error(f"Error procesando fuente {filename} para cuaderno {notebook_id}: {e}")
            metadata = self._load_metadata()
            if notebook_id in metadata:
                for src in metadata[notebook_id]["sources"]:
                    if src["id"] == source_id:
                        src["status"] = "error"
                        src["error"] = str(e)
                        break
                self._save_metadata(metadata)

    async def investigar_y_crear_cuaderno(self, tema: str, provider_api_key: str | None = None) -> dict:
        title = f"Investigación: {tema}"
        description = f"Cuaderno generado automáticamente por el Agente sobre '{tema}'"
        notebook = self.create_cuaderno(title, description)
        notebook_id = notebook["id"]
        notebook["research"] = self._set_research(notebook_id, "running")

        # Run auto research background task
        asyncio.create_task(self._run_auto_research(notebook_id, tema, provider_api_key))

        return notebook

    def _set_research(self, notebook_id: str, status: str, error: str | None = None) -> dict:
        """Persist the auto-research state ('running', 'done' or 'error') so clients can show progress and failures."""
        research = {"status": status, "error": error}
        metadata = self._load_metadata()
        if notebook_id in metadata:
            metadata[notebook_id]["research"] = research
            self._save_metadata(metadata)
        return research

    async def _run_auto_research(self, notebook_id: str, tema: str, provider_api_key: str | None = None):
        try:
            from cognitivo.skills.websearch_tool import WebSearchEngine

            search_engine = WebSearchEngine()

            queries = [tema, f"{tema} conceptos clave e investigación", f"{tema} resumen y datos principales"]

            logger.info(f"Iniciando investigación autónoma sobre '{tema}' para cuaderno {notebook_id}...")

            gathered_texts = []
            last_error = "sin resultados"
            for q in queries:
                try:
                    resp = await search_engine.buscar(q, max_results=4)
                    if resp.status == "success" and resp.results:
                        for item in resp.results:
                            snippet = clean_web_text(item.snippet)
                            if snippet:
                                gathered_texts.append(f"### Fuente: {item.title}\nURL: {item.url}\n\n{snippet}")
                    else:
                        last_error = resp.error or last_error
                except Exception as err:
                    logger.warning(f"Error en búsqueda web '{q}': {err}")
                    last_error = str(err)

            if not gathered_texts:
                raise WebSearchError(f"La búsqueda web sobre '{tema}' no devolvió resultados ({last_error}).")

            combined_content = "\n\n---\n\n".join(gathered_texts)
            safe_filename = f"Investigacion_Web_{re.sub(r'[^a-zA-Z0-9_]', '_', tema)[:25]}.txt"

            await self.add_fuente(
                notebook_id,
                safe_filename,
                combined_content.encode("utf-8"),
                description=f"Hallazgos de investigación sobre {tema}",
                index_in_background=False,
            )

            # Auto generate syntheses (the source is already indexed, so they get its context)
            await self.generar_sintesis(notebook_id, "resumen", provider_api_key)
            await self.generar_sintesis(notebook_id, "guia_estudio", provider_api_key)

            self._set_research(notebook_id, "done")
            logger.info(f"Investigación autónoma completada exitosamente para cuaderno {notebook_id}.")

        except Exception as e:
            logger.error(f"Error en auto-investigación para cuaderno {notebook_id}: {e}")
            self._set_research(notebook_id, "error", str(e))

    def query_cuaderno_context(self, notebook_id: str, query: str, top_k: int = 5) -> list[dict]:
        """Notebook chunks nearest to the query. A failed search raises: it is not an empty notebook."""
        try:
            self.table = self.db.open_table("cuadernos_chunks")
        except Exception:
            pass
        query_vec = self.embedder.embed_query(query)
        return (
            self.table.search(query_vec)
            .where(f"notebook_id = {sql_string_literal(notebook_id)}")
            .limit(top_k)
            .to_list()
        )

    async def _completar(self, messages: list[dict], provider_api_key: str | None) -> str:
        """One LLM completion. A failure raises NotebookLLMError; there is no fallback text."""
        import litellm

        api_key = provider_api_key or os.environ.get("OPENROUTER_API_KEY")
        model = "openrouter/google/gemini-1.5-pro" if api_key else "gpt-3.5-turbo"
        kwargs = {"model": model, "messages": messages, "temperature": 0.3}
        if api_key:
            kwargs["api_key"] = api_key
        try:
            response = await asyncio.to_thread(litellm.completion, **kwargs)
            return response.choices[0].message.content
        except Exception as e:
            raise NotebookLLMError(f"El modelo de lenguaje no respondió: {e}") from e

    def _guardar_nota(self, notebook_id: str, title: str, tipo: str, content: str) -> dict:
        note_entry = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "type": tipo,
            "content": content,
            "created_at": datetime.now().isoformat(),
        }
        # Reload: the snapshot taken before the LLM call may be stale (e.g. background indexing saved meanwhile).
        metadata = self._load_metadata()
        if notebook_id not in metadata:
            raise NotebookNotFoundError(f"Cuaderno {notebook_id} no existe.")
        metadata[notebook_id]["notes"].append(note_entry)
        self._save_metadata(metadata)
        return note_entry

    async def _escribir_informe(
        self, notebook_id: str, consulta: str, hallazgos: str, provider_api_key: str | None
    ) -> dict:
        """Deep-search report note, written by the LLM from the web findings."""
        system_prompt = (
            "Eres el Investigador de Visión OS. Redacta un informe de investigación profunda basándote ÚNICAMENTE "
            "en los siguientes resultados de búsqueda web. Cita cada dato con su fuente usando el formato "
            "[Fuente N] y termina con la lista de las fuentes citadas (título y URL).\n\n"
            f"--- RESULTADOS WEB ---\n{hallazgos}\n----------------------\n\n"
            "Formatea tu respuesta utilizando Markdown impecable con encabezados y viñetas."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Tema del informe: {consulta}"},
        ]
        informe = await self._completar(messages, provider_api_key)
        return self._guardar_nota(notebook_id, f"Informe: {consulta[:30]}", "informe_profundo", informe)

    async def generar_sintesis(
        self, notebook_id: str, tipo_sintesis: str = "resumen", provider_api_key: str | None = None
    ) -> dict:
        self.ensure_cuaderno(notebook_id)

        chunks = self.query_cuaderno_context(notebook_id, "resumen general e ideas principales", top_k=15)
        if not chunks:
            raise EmptyNotebookError(EMPTY_NOTEBOOK_MESSAGE)
        context_text = "\n\n".join([f"[Fuente: {c['source_name']}]\n{c['text']}" for c in chunks])

        prompts = {
            "resumen": "Genera un Resumen Ejecutivo claro y estructurado con los puntos clave del cuaderno.",
            "guia_estudio": "Genera una Guía de Estudio detallada con glosario de términos clave, conceptos centrales y ejercicios de autoevaluación.",
            "faq": "Genera un listado de Preguntas Frecuentes (FAQ) con sus respuestas fundamentadas exactamente en las fuentes.",
            "podcast_script": "Genera un Guion de Podcast informal y dinámico entre dos locutores (Alex y Sam) debatiendo el contenido de las fuentes.",
        }

        user_prompt = prompts.get(tipo_sintesis, prompts["resumen"])
        system_prompt = (
            "Eres el Sintetizador Cognitivo de Visión OS. Tu tarea es generar la síntesis solicitada "
            "basándote ÚNICAMENTE en el siguiente contexto de las fuentes proporcionadas.\n\n"
            f"--- CONTEXTO ---\n{context_text}\n----------------\n\n"
            "Formatea tu respuesta utilizando Markdown impecable con encabezados y viñetas."
        )

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        generated_text = await self._completar(messages, provider_api_key)
        return self._guardar_nota(notebook_id, f"Síntesis: {tipo_sintesis.capitalize()}", tipo_sintesis, generated_text)

    async def chat_cuaderno_stream(
        self,
        notebook_id: str,
        query: str,
        history: list[dict] | None = None,
        search_web: bool = False,
        max_web_results: int = 5,
        response_style: str = "conciso",
        provider_api_key: str | None = None,
    ) -> AsyncGenerator[str, None]:
        # Validate before the first yield so an unknown or crafted id never reaches the filesystem.
        self.ensure_cuaderno(notebook_id)
        clean_query = query.replace("@web", "").strip() if query.strip().startswith("@web") else query.strip()

        if search_web or query.strip().startswith("@web") or max_web_results > 10:
            mode_label = "Profunda (>20 fuentes)" if max_web_results > 10 else f"Simple ({max_web_results} fuentes)"
            yield f"[🌐 Buscando en la web en modo {mode_label} e indexando fuentes en el cuaderno...]\n\n"
            from cognitivo.skills.websearch_tool import WebSearchEngine

            resp = await WebSearchEngine().buscar(clean_query, max_results=max_web_results)
            gathered_texts = []
            if resp.status == "success" and resp.results:
                for i, item in enumerate(resp.results):
                    snippet = clean_web_text(item.snippet)
                    if snippet:
                        gathered_texts.append(f"### Fuente [{i + 1}]: {item.title}\nURL: {item.url}\n\n{snippet}")
            if not gathered_texts:
                reason = resp.error or "sin resultados"
                raise WebSearchError(f"La búsqueda web sobre '{clean_query}' no devolvió resultados ({reason}).")

            combined_content = "\n\n---\n\n".join(gathered_texts)
            safe_filename = f"Investigacion_Web_{re.sub(r'[^a-zA-Z0-9_]', '_', clean_query)[:25]}.txt"
            await self.add_fuente(
                notebook_id,
                safe_filename,
                combined_content.encode("utf-8"),
                description=f"Búsqueda web ({mode_label}) para query: {clean_query[:30]}",
                index_in_background=False,
            )
            if max_web_results > 10:
                await self._escribir_informe(notebook_id, clean_query, combined_content, provider_api_key)

        fetch_top_k = 15 if max_web_results > 10 else 6
        chunks = self.query_cuaderno_context(notebook_id, clean_query, top_k=fetch_top_k)
        if not chunks:
            raise EmptyNotebookError(EMPTY_NOTEBOOK_MESSAGE)

        context_blocks = "\n\n".join([f"--- [Fuente: {c['source_name']}] ---\n{c['text']}" for c in chunks])

        if response_style == "conciso":
            style_instruction = "ESTILO DE RESPUESTA: Responde de forma concisa, directa y sintética al grano. Utiliza viñetas breves si ayuda a la claridad."
        elif response_style == "abierto":
            style_instruction = "ESTILO DE RESPUESTA: Responde de forma amplia, profunda y explicativa. Desarrolla el contexto y conecta los conceptos de las fuentes proporcionando explicaciones detalladas y completas."
        else:
            style_instruction = "ESTILO DE RESPUESTA: Responde de manera estructurada y balanceada."

        system_prompt = (
            "Eres el Asistente del Cuaderno de Visión OS.\n"
            "REGLAS OBLIGATORIAS:\n"
            "1. Responde a la pregunta del usuario utilizando ÚNICAMENTE la siguiente información extraída de las fuentes adjuntas.\n"
            "2. Cita siempre la fuente correspondiente en tus respuestas utilizando el formato [Fuente: nombre_archivo].\n"
            "3. REGLA DE ORO: Si la respuesta no está contenida explícitamente en las fuentes, responde strictly: "
            "'No encuentro información sobre este tema en las fuentes de este cuaderno.'\n"
            f"4. {style_instruction}\n\n"
            f"=== FUENTES DEL CUADERNO ===\n{context_blocks}\n============================="
        )

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for h in history[-6:]:
                messages.append({"role": h.get("role", "user"), "content": h.get("text", h.get("content", ""))})
        messages.append({"role": "user", "content": clean_query})

        import litellm

        api_key = provider_api_key or os.environ.get("OPENROUTER_API_KEY")
        model = "openrouter/google/gemini-1.5-pro" if api_key else "gpt-3.5-turbo"

        try:
            kwargs = {"model": model, "messages": messages, "stream": True, "temperature": 0.2}
            if api_key:
                kwargs["api_key"] = api_key

            response = await asyncio.to_thread(litellm.completion, **kwargs)
            for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    yield delta
                    await asyncio.sleep(0.01)
        except Exception as e:
            raise NotebookLLMError(f"El modelo de lenguaje no respondió: {e}") from e
