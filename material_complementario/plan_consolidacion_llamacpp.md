# Plan de Implementación: Consolidación del Motor Llama.cpp (Visión OS & Studio)

Consolidar la integración y gestión del ciclo de vida de `llama-server.exe` entre el backend Python (`cognitivo/gestor_llamacpp.py` y `sentidos/sistema_periferico.py`) y el panel de ajustes frontend de Tauri (`vision_studio/src/components/Settings/LlamaCppPanel.tsx`).

## Objetivos
1. Asegurar linteo impecable (`ruff check`) y 100% de éxito en la suite de pruebas unitarias (`pytest tests/`).
2. Implementar cobertura de tests unitarios dedicada (`tests/unit/test_gestor_llamacpp.py`) para `GestorLlamaCpp`.
3. Fortalecer el manejo de ciclo de vida del subproceso `llama-server.exe` y la tolerancia a fallos en el frontend React (`LlamaCppPanel.tsx`).

## Cambios Propuestos

### Core & Backend (`cognitivo/` y `sentidos/`)
- **[gestor_llamacpp.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/gestor_llamacpp.py)**:
  - Formatear imports según la especificación de Ruff.
  - Robustecer lanzamiento de subprocesos y captura de errores de puertos/rutas.
- **[sistema_periferico.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/sentidos/sistema_periferico.py)**:
  - Formatear importación de `gestor_llamacpp`.
  - Asegurar respuestas limpias en errores de API `/api/llamacpp/*`.

### Pruebas Unitarias (`tests/`)
- **[test_gestor_llamacpp.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/tests/unit/test_gestor_llamacpp.py)**:
  - Cobertura completa para `verificar_estado_servidor`, `obtener_telemetria_sistema`, `generar_script_bat`, e inicio/detención de servidor con mocks.

### Frontend (`vision_studio/`)
- **[LlamaCppPanel.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Settings/LlamaCppPanel.tsx)**:
  - Resiliencia frente a puertos dinámicos del Gateway y experiencia de usuario fluida durante estados de transición.

---

## Verificación
- Execución de linteo: `.venv\Scripts\ruff check core/ cognitivo/ sentidos/ memoria/ tests/`
- Ejecución de pruebas: `.venv\Scripts\pytest tests/`
