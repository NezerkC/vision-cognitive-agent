# Plan de Implementación: Reactividad Real de llama-server y Presets Oficiales de Proveedores

Este plan responde al feedback del usuario para:
1. **Hacer reactivo y real el botón "Iniciar Servidor"**: Reemplazar la simulación por el control de subproceso real (vía endpoints FastAPI / comandos nativos de Tauri y `gestor_llamacpp.py`), matando cualquier servidor viejo para liberar VRAM antes de levantar el nuevo.
2. **Healthcheck en tiempo real**: Comprobar la disponibilidad real del puerto `http://localhost:8080/health` o `/v1/models` para refrescar el badge de estado.
3. **Presets Oficiales de Proveedores**: Cargar automáticamente las configuraciones recomendadas por los creadores de los modelos (Qwen, Gemma 4, DeepSeek R1, Llama 3.2, Mistral) con las banderas CLI **exactas** que acepta `llama-server.exe` (build b10082 con CUDA 13.3).

---

## Verificación de Sintaxis de Banderas de `llama-server.exe`

Hemos verificado las banderas contra el ejecutable oficial `llama-server.exe` (`b10082`):

| Parámetro | Bandera CLI Exacta en llama-server | Valores / Ejemplo | Propósito |
|-----------|-------------------------------------|-------------------|-----------|
| **GPU Layers** | `-ngl <N>` o `--n-gpu-layers <N>` | `-ngl 999` | Capas descargadas a la GPU |
| **Context Size** | `-c <N>` o `--ctx-size <N>` | `-c 131072` | Tamaño máximo de la ventana de contexto |
| **KV Cache K** | `-ctk <tipo>` o `--cache-type-k <tipo>` | `-ctk q4_0` | Cuantización KV K (`f16`, `q8_0`, `q4_0`) |
| **KV Cache V** | `-ctv <tipo>` o `--cache-type-v <tipo>` | `-ctv q4_0` | Cuantización KV V (`f16`, `q8_0`, `q4_0`) |
| **Flash Attention** | `-fa <on/off>` o `--flash-attn <on/off>` | `-fa on` | Aceleración de atención por GPU |
| **Temperatura** | `--temp <N>` | `--temp 0.7` | Grado de aleatoriedad del muestreo |
| **Top-P** | `--top-p <N>` | `--top-p 0.9` | Muestreo nucleus |
| **Speculative Decoding** | `--spec-type <tipo>` | `--spec-type draft-mtp` | Tipo MTP para inferencia rápida |
| **Draft Tokens Max** | `--spec-draft-n-max <N>` | `--spec-draft-n-max 2` | Límite draft de tokens MTP (slider 1 a 10) |
| **Puerto & Host** | `--port <P> --host <H>` | `--port 8080 --host 127.0.0.1` | Puerto HTTP y enlace de IP local |

---

## User Review Required

> [!IMPORTANT]
> - **Control Real de Subproceso**: Al hacer clic en "Iniciar Servidor", la app enviará la petición al backend (`sistema_periferico.py` / `gestor_llamacpp.py`), arrancará `llama-server.exe` con las banderas verificadas arriba y se mantendrá el monitoreo en vivo del subproceso.
> - **Manejo de VRAM y Garantía OOM**: Si ya existe un servidor corriendo en el puerto 8080, el gestor lo detendrá de forma limpia antes de levantar el nuevo modelo para evitar conflictos de puerto y saturación de la VRAM GPU.

---

## Proposed Changes

### Backend: Python (`gestor_llamacpp.py` y `sistema_periferico.py`)

#### [MODIFY] [sistema_periferico.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/sentidos/sistema_periferico.py)
- Agregar endpoints REST para el control del servidor Llama.cpp:
  - `POST /api/llamacpp/iniciar`: Detiene la instancia previa, lee la ruta de binarios y banderas, y ejecuta `iniciar_servidor_llamacpp()`.
  - `POST /api/llamacpp/detener`: Detiene limpia y completamente el subproceso de `llama-server.exe` liberando VRAM.
  - `GET /api/llamacpp/estado`: Retorna si el proceso está activo y realiza ping a `http://localhost:8080/health`.

#### [MODIFY] [gestor_llamacpp.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/gestor_llamacpp.py)
- Agregar diccionario de configuraciones oficiales recomendadas por proveedores (`PROVIDER_RECOMMENDATIONS`) usando las banderas CLI comprobadas:
  - **Qwen (Alibaba Cloud)**: `-ngl 999 -fa on -ctk q4_0 -ctv q4_0 -c 131072 --temp 0.7 --top-p 0.8 --spec-type draft-mtp --spec-draft-n-max 2`.
  - **Gemma 4 / 2 (Google DeepMind)**: `-ngl 99 -fa on -ctk q8_0 -ctv q8_0 -c 32768 --temp 0.6 --top-p 0.9`.
  - **DeepSeek R1 (DeepSeek AI)**: `-ngl 999 -fa on -ctk q4_0 -ctv q4_0 -c 65536 --temp 0.6 --top-p 0.95 --spec-type draft-mtp --spec-draft-n-max 3`.
  - **Llama 3.2 / 3.1 (Meta AI)**: `-ngl 999 -fa on -ctk q8_0 -ctv q8_0 -c 131072 --temp 0.7 --top-p 0.9`.
  - **Mistral / Mixtral (Mistral AI)**: `-ngl 999 -fa on -ctk f16 -ctv f16 -c 32768 --temp 0.7 --top-p 0.9`.

---

### Frontend: Vision Studio UI

#### [MODIFY] [LlamaCppPanel.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Settings/LlamaCppPanel.tsx)
- Reemplazar la simulación de `setTimeout` en `handleToggleServer` por llamadas reales a `POST /api/llamacpp/iniciar` y `POST /api/llamacpp/detener`.
- Agregar un efecto de polling (`setInterval` cada 3s) a `http://localhost:8080/health` o `/api/llamacpp/estado` para reflejar el estado real del servidor.
- Agregar selector de **Presets de Proveedores Oficiales** que auto-complete las banderas verificadas (`-ngl`, `-c`, `-ctk`, `-ctv`, `-fa`, `--temp`, `--top-p`, `--spec-draft-n-max`).

---

## Verification Plan

### Automated Tests
- Ejecutar `python cognitivo/gestor_llamacpp.py` verificando la sintaxis CLI en `PROVIDER_RECOMMENDATIONS`.
- Probar llamadas HTTP a `/api/llamacpp/iniciar` y `/api/llamacpp/detener`.

### Manual Verification
1. Abrir **Vision Studio** -> Configuración -> Modelos -> Motor Llama.cpp.
2. Hacer clic en **Iniciar Servidor** y comprobar en la Consola del sistema o Administrador de tareas que `llama-server.exe` arrancó realmente.
3. Cambiar a otro preset (ej: Gemma 4 a Qwen 35B) e Iniciar Servidor de nuevo; verificar que la instancia vieja se cierre y la nueva tome la VRAM.
4. Enviar un mensaje desde el chat de Vision y verificar que la inferencia responda de forma fluida.
