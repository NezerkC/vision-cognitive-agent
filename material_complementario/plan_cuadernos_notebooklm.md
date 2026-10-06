# Plan de Implementación: Módulo "Cuadernos" (NotebookLM Integrado)

Crear un módulo dedicado de **Cuadernos** dentro de Visión OS y Visión Studio que funcione de manera análoga a Google NotebookLM. Permitirá a los usuarios crear cuadernos temáticos, adjuntar fuentes (archivos PDF, documentos TXT/MD, enlaces y notas), generar síntesis/guías de estudio basadas estrictamente en esas fuentes y chatear con el modelo contextualizado en el cuaderno activo.

---

## User Review Required

> [!IMPORTANT]
> **Formato de Almacenamiento**: Las fuentes de los cuadernos se almacenarán en `memoria_activa/cuadernos/` indexadas en **LanceDB** mediante tags de `notebook_id` para garantizar búsquedas semánticas (RAG) rápidas y acotadas.

> [!NOTE]
> **Integración Frontend**: Se agregará una nueva pestaña en la `ActivityBar` de Visión Studio con un icono de Cuaderno (`BookOpen`) que desplegará el gestor de cuadernos y sus fuentes.

---

## Proposed Changes

### Backend (`cognitivo` & `sentidos`)

---

#### [NEW] [cuadernos_manager.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/cuadernos_manager.py)
- Gestor backend para la creación, listado y eliminación de Cuadernos.
- Lógica de subida de fuentes (procesamiento de PDFs con `PyPDFLoader`, división en fragmentos e indexación en LanceDB etiquetados por `notebook_id`).
- Motor de síntesis: funciones para generar resúmenes automáticos, guías de estudio, preguntas frecuentes (FAQ) y resúmenes estructurados basados únicamente en las fuentes adjuntas al cuaderno.
- Endpoint RAG acotado al cuaderno activo.

#### [MODIFY] [sistema_periferico.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/sentidos/sistema_periferico.py)
- Exponer rutas REST FastAPI para cuadernos:
  - `GET /api/cuadernos`
  - `POST /api/cuadernos`
  - `DELETE /api/cuadernos/{id}`
  - `POST /api/cuadernos/{id}/fuentes` (Acepta multipart PDF/TXT/MD o URL)
  - `POST /api/cuadernos/{id}/sintesis`
  - `POST /api/cuadernos/{id}/chat`

---

### Frontend (`vision_studio`)

---

#### [MODIFY] [useSettingsStore.ts](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/stores/useSettingsStore.ts)
- Agregar `'notebooks'` al tipo `ActiveTab` y al estado del store.

#### [MODIFY] [ActivityBar.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Layout/ActivityBar.tsx)
- Agregar el botón de la pestaña **Cuadernos** (`BookOpen` icon) en la ActivityBar.

#### [NEW] [NotebooksView.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Notebooks/NotebooksView.tsx)
- Componente principal del módulo de Cuadernos:
  - **Barra lateral de Cuadernos**: Listado de cuadernos del usuario y botón "Nuevo Cuaderno".
  - **Panel de Fuentes**: Zona de carga drag & drop para PDFs, TXT y enlaces web. Lista de fuentes adjuntas con estado de indexación.
  - **Panel de Estudio y Síntesis**: Botones de acción rápida ("Generar Resumen Exec", "Guía de Estudio", "Preguntas Frecuentes", "Audio Podcast (Mock)").
  - **Chat Acotado (Grounded Chat)**: Interfaz de chat que consulta únicamente la memoria del cuaderno activo con citación de fuentes.

#### [MODIFY] [SidebarComponents.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Sidebar/SidebarComponents.tsx)
- Renderizar `<NotebooksView />` cuando `activeTab === 'notebooks'`.

---

## Verification Plan

### Automated Tests
- Ejecutar la suite de Pytest para verificar la creación e ingestión de cuadernos:
  ```bash
  pytest tests/test_cuadernos.py
  ```
- Ejecutar linter Ruff para garantizar cero errores de código Python:
  ```bash
  ruff check cognitivo/ sentidos/
  ```

### Manual Verification
- Iniciar Visión Studio (`npm run dev` en `vision_studio`).
- Crear un cuaderno nuevo (ej. "Investigación Visión OS").
- Arrastrar un archivo PDF a la zona de fuentes y verificar que se extraiga e indexe correctamente.
- Probar la generación de un Resumen y realizar preguntas en el Chat acotado comprobando que las respuestas provengan del PDF subido.
