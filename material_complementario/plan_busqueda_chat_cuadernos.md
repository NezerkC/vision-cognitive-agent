# Plan de Implementación: Creación de Nuevo Cuaderno, Vinculación Semántica e Inyección Dual

Ajuste del flujo de búsqueda web: al realizar una investigación por un tópico encargado, **siempre se crea un nuevo cuaderno dedicado**, se efectúa la **vinculación semántica** con un cuaderno pre-existente afín (si existe) y **se inyecta automáticamente la nueva fuente e información en ambos cuadernos** (el nuevo y el vinculado).

---

## 🧠 Análisis y Arquitectura del Diseño

### 1. Inyección Dual y Vinculación Semántica
1. **Creación Autónoma del Nuevo Cuaderno**:
   - Cada investigación por tópico genera un nuevo cuaderno dedicado: `Investigación: [Tópico]`.
2. **Evaluación de Relación Semántica**:
   - Se mide la similitud entre el tópico investigado y la base de cuadernos del usuario.
3. **Inyección Dual de Información**:
   - Si la similitud supera el umbral (0.50) con un cuaderno existente (ej. `Cuaderno_Existente`):
     - Se vinculan mutuamente mediante `related_notebook_id`.
     - Se guardan las nuevas fuentes descargadas (`Investigacion_Web_[topico].txt`) en **ambos cuadernos** (`Nuevo_Cuaderno` y `Cuaderno_Existente`).
     - Se indexan los vectores en LanceDB asociados a los IDs de **ambos cuadernos**, alimentando el contexto RAG de ambos.
     - Se visualiza el badge `🔗 Vinculado a: [Cuaderno_Existente]` en Visión Studio.

---

## 🛠️ Cambios Propuestos

### Componente Backend (`cognitivo` & `sentidos`)

#### [MODIFY] [cuadernos_manager.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/cuadernos_manager.py)
- Modificar `_run_auto_research` y `add_fuente`:
  - Al completar la búsqueda web del nuevo cuaderno:
  - Verificar si existe un cuaderno relacionado afín (`_find_related_notebook`).
  - De existir relación:
    1. Asignar `related_notebook_id` y `related_notebook_title` al nuevo cuaderno.
    2. Duplicar la entrada de la fuente e invocar `_process_and_index_source` para el `notebook_id` del **cuaderno vinculado**, enriqueciendo ambos cuadernos simultáneamente.

#### [MODIFY] [sistema_periferico.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/sentidos/sistema_periferico.py)
- Retornar en la respuesta de `POST /api/cuadernos/investigar` la confirmación de la inyección dual cuando aplique vinculación.

---

### Componente Frontend (`vision_studio`)

#### [MODIFY] [NotebooksView.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Notebooks/NotebooksView.tsx)
- En la vista del Cuaderno:
  - Mostrar badge de vinculación semántica con acceso directo al cuaderno relacionado.
  - Al navegar al cuaderno vinculado, verificar que la nueva fuente web aparezca también incorporada en su listado de fuentes.

---

## 🧪 Plan de Verificación

### Pruebas Automatizadas
- Actualizar `tests/unit/test_cuadernos.py`:
  - `test_investigar_con_inyeccion_dual`:
    1. Crear cuaderno previo *"Machine Learning y Redes Neuronales"*.
    2. Auto-investigar el tópico *"Redes Convolucionales CNN"*.
    3. Verificar que se cree el **nuevo cuaderno** `Investigación: Redes Convolucionales CNN`.
    4. Verificar que **ambos cuadernos** (el previo y el nuevo) contengan la fuente `Investigacion_Web_Redes_Convolucionales_CNN.txt` y sus chunks indexados en LanceDB.
- Ejecutar suite de calidad:
  ```bash
  .venv\Scripts\pytest tests/unit/test_cuadernos.py
  .venv\Scripts\ruff check core/ cognitivo/ sentidos/ memoria/ tests/
  ```

### Verificación Manual
1. Ejecutar auto-investigación sobre un tema afín a un cuaderno existente.
2. Confirmar que se genera el nuevo cuaderno y que al abrir el cuaderno vinculado anterior, la nueva fuente web también figure disponible e indexada.
