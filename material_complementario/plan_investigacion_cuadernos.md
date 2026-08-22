# Plan de Implementación: Investigación Autónoma y Auto-Organización de Cuadernos

Habilitar al modelo de Visión OS para que realice investigaciones autónomas en la web sobre cualquier tema indicado por el usuario, cree automáticamente un **Cuaderno**, guarde y clasifique las fuentes recuperadas y genere resúmenes/síntesis estructurados de manera independiente.

---

## User Review Required

> [!IMPORTANT]
> **Integración con Motor de Búsqueda Web**: Se utilizará `WebSearchEngine` (`cognitivo/skills/websearch_tool.py`) para realizar múltiples consultas sobre el tema, extrayendo artículos y resúmenes web que se indexarán como fuentes oficiales en LanceDB.

> [!NOTE]
> **Autogestión de Cuadernos**: El modelo no solo buscará la información, sino que creará la estructura completa del cuaderno (Fuentes, Resumen Ejecutivo, Guía de Estudio y FAQ) sin requerir intervención manual del usuario.

---

## Proposed Changes

### Backend (`cognitivo` & `sentidos`)

---

#### [MODIFY] [cuadernos_manager.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/cuadernos_manager.py)
- Agregar método `investigar_y_crear_cuaderno(tema: str, provider_api_key: Optional[str] = None)`:
  1. Crear un cuaderno titulado `"Investigación: {tema}"`.
  2. Ejecutar búsquedas web automáticas sobre el tema usando `WebSearchEngine`.
  3. Formatear y guardar los hallazgos como archivos de texto de fuentes en `memoria_activa/cuadernos/sources/`.
  4. Procesar e indexar las fuentes halladas en **LanceDB** (`cuadernos_chunks`).
  5. Generar automáticamente notas de síntesis (`resumen`, `guia_estudio` y `faq`).

#### [MODIFY] [sistema_periferico.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/sentidos/sistema_periferico.py)
- Exponer nuevo endpoint REST:
  - `POST /api/cuadernos/investigar` (Recibe `{ "tema": "...", "api_key": "..." }`).

---

### Frontend (`vision_studio`)

---

#### [MODIFY] [NotebooksView.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Notebooks/NotebooksView.tsx)
- Agregar botón **"Auto-Investigar con IA"** (`Sparkles` / `Search` icon) en el panel de Cuadernos.
- Modal / Cuadro de diálogo para ingresar el tema a investigar (ej. *"Computación Cuántica y Qubits"*).
- Indicador de estado de investigación activa (*"Buscando en la web, indexando fuentes y sintetizando cuaderno..."*).
- Selección e iluminación automática del cuaderno recién generado al finalizar la tarea.

---

## Verification Plan

### Automated Tests
- Agregar prueba unitaria en `tests/unit/test_cuadernos.py` para validar el flujo `investigar_y_crear_cuaderno`:
  ```bash
  .venv\Scripts\pytest tests/unit/test_cuadernos.py
  ```
- Ejecutar linter Ruff para garantizar cero errores de código Python:
  ```bash
  .venv\Scripts\ruff check core/ cognitivo/ sentidos/ memoria/ tests/
  ```

### Manual Verification
- En Visión Studio ([http://localhost:1420/](http://localhost:1420/)), abrir el apartado **Cuadernos**.
- Hacer clic en **Auto-Investigar con IA** e ingresar un tema (ej. *"Modelos de Lenguaje Locales con Ollama"*).
- Verificar que se cree el cuaderno, se descarguen e indexen las fuentes web y se generen automáticamente el Resumen y la Guía de Estudio.
