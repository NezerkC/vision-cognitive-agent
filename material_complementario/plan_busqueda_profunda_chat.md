# Plan de Implementación: Modos de Búsqueda de Información (Simple vs. Profunda) en Chat de Cuadernos

Agregar botones de configuración e interacción en la interfaz del chat del cuaderno activo para permitir la búsqueda de información respecto a la conversación actual. El usuario podrá elegir entre una búsqueda **Simple** (rápida, 5 fuentes) y una búsqueda **Profunda** (exhaustiva, >20 fuentes incluyendo foros, vídeos, documentación y páginas web), indexando automáticamente los hallazgos en el cuaderno actual y **generando un informe estructurado con citas explícitas de todos los archivos y fuentes recolectados en la sección de Notas/Síntesis del cuaderno**.

## Clasificación de Entrega & Git Branch

- **Tipo de Entrega**: `feat`
- **Nombre de Rama**: `feat/busqueda-profunda-cuadernos`
- **Prefijo Conventional Commit**: `feat:`

## Requerimiento Especial
- **Informe de Citas**: Al ejecutar una búsqueda profunda, además de indexar las >20 fuentes y utilizarlas para responder en el chat, el sistema creará automáticamente una nota en el cuaderno con el informe completo que relaciona las fuentes e incluye citas numéricas/URLs a todos los archivos y sitios consultados.

## Cambios Propuestos

### Frontend (`vision_studio`)
- `vision_studio/src/components/Notebooks/NotebooksView.tsx`:
  - Botones/Selectores de modo de búsqueda en la pestaña Chat: **Simple** (5 fuentes) vs **Profunda** (>20 fuentes: foros, webs, vídeos, datos).
  - Botón de acción rápida sobre el chat: *"Buscá información sobre este dato"* para ejecutar la búsqueda sobre el último concepto o mensaje.
  - Renderizado de badges/links a más de 20 fuentes en los resultados y notificación del informe generado en las Notas.

### Backend (`cognitivo` y `sentidos`)
- `cognitivo/cuadernos_manager.py`:
  - Modificar `chat_cuaderno_stream` para procesar búsquedas profundas que extraigan >20 resultados divididos en categorías (páginas web, foros como Reddit/StackOverflow, referencias multimedia y datos).
  - Guardar e indexar automáticamente el lote masivo de fuentes en LanceDB para el cuaderno.
  - Generar automáticamente una Nota de Síntesis / Informe con citas estructuradas.
- `cognitivo/skills/websearch_tool.py`:
  - Expandir `WebSearchEngine` para consultas multimodales/multi-categoría paralelas deduplicadas.
- `sentidos/sistema_periferico.py`:
  - Actualizar `/api/cuadernos/{notebook_id}/chat` para recibir los parámetros `search_mode` y `search_depth`.

## Plan de Verificación

1. **Pruebas Automatizadas**:
   - `pytest tests/unit/test_cuadernos.py`
   - `ruff check core/ cognitivo/ sentidos/ memoria/ tests/`
2. **Verificación Manual**:
   - Abrir Visión Studio, ir a un cuaderno, activar la pestaña Chat, cambiar a Búsqueda Profunda y solicitar buscar información sobre un dato. Verificar que la respuesta cite e indexe más de 20 fuentes diversas con links a foros, webs y datos, y que se cree la Nota de Informe con Citas.
