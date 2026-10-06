# Walkthrough: Modos de Búsqueda de Información y Generación de Informes con Citas en Chat de Cuadernos

Se implementó con éxito la funcionalidad de selección de modo de búsqueda (**Simple** vs. **Profunda**) en la interfaz de chat de los cuadernos de Visión OS, permitiendo consultar más de 20 fuentes diversas (foros, páginas web, vídeos y datos) y generando automáticamente un **Informe de Investigación Profunda con Citas Estructuradas** en las Notas del cuaderno.

## Cambios Realizados

### 1. Backend Cognitivo y Sentidos (Python)
- **`cognitivo/skills/websearch_tool.py`**:
  - Se amplió el límite máximo de resultados a 50.
  - Se agregó el método `buscar_profundo(query, max_results=25)` para ejecutar búsquedas paralelas por categorías (web general, foros de comunidad como Reddit/StackOverflow, tutoriales/vídeos y sitios de datos), agregando y deduplicando más de 20 enlaces y fragmentos.
- **`cognitivo/cuadernos_manager.py`**:
  - Se adaptó `chat_cuaderno_stream` para procesar búsquedas en modo profundo (`max_web_results > 10`), extrayendo más de 20 fuentes e indexándolas en LanceDB.
  - Se agregó la creación automática de una nota en el cuaderno tipo `informe_profundo` titulada **"Informe de Investigación Profunda"**, que consolida todas las fuentes encontradas con enlaces y citas estructuradas.
  - Se amplió el contexto RAG (`top_k = 15`) para búsquedas profundas.
- **`sentidos/sistema_periferico.py`**:
  - Se actualizó el endpoint `POST /api/cuadernos/{notebook_id}/chat` para interpretar los parámetros `search_mode` (`"simple"` | `"profundo"`).

### 2. Frontend Visión Studio (`vision_studio`)
- **`vision_studio/src/components/Notebooks/NotebooksView.tsx`**:
  - Se añadieron botones de selector de modo en la barra de controles del chat:
    - **Simple (5 fuentes)**: Búsqueda rápida tradicional.
    - **Profunda (>20 fuentes)**: Búsqueda extendida e indexación masiva.
  - Se agregó un botón de acción directa sobre la entrada del chat:
    - **"Buscá información profunda al respecto de este dato"**: Ejecuta la búsqueda profunda de más de 20 fuentes sobre la conversación actual o la consulta escrita y genera el informe de citas.
  - Se actualizó el flujo de envío `handleSendChat` para sincronizar las notas automáticamente al finalizar la búsqueda.

---

## Verificación Realizada

### 1. Pruebas Automatizadas
- **Suite de Pruebas Unitarias de Cuadernos**:
  Se agregó la prueba `test_chat_cuaderno_stream_busqueda_profunda` en `tests/unit/test_cuadernos.py`.
  - Resultado: Todos los tests pasaron exitosamente.
- **Linter de Código (Ruff)**:
  Se ejecutó `ruff check core/ cognitivo/ sentidos/ memoria/ tests/`.
  - Resultado: `All checks passed!` (0 advertencias/errores).

### 2. Documentación y Control de Cambios
- Los cambios se realizaron en la rama de trabajo `feat/busqueda-profunda-cuadernos`.
- Se guardó el plan y registro de entregas en la carpeta personal de documentación:
  - `material_complementario/plan_busqueda_profunda_chat.md`
  - `material_complementario/walkthrough_busqueda_profunda_chat.md`
