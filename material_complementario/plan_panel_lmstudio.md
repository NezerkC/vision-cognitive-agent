# Plan de Implementación: Panel de Configuración Estilo LM Studio (Motor Llama.cpp, Ollama, LM Studio)

Este plan detalla el diseño e implementación del panel de control de modelos e inferencia local inspirado en **LM Studio**, integrado dentro de Vision Studio. Permitirá a los usuarios gestionar el servidor ejecutable (`llama-server.exe` / `.bat`), monitorear uso de VRAM/GPU, hardware del sistema (RAM, CPU, discos SSD/HDD y temperaturas), ajustar hiperparámetros de inferencia (contexto, capas GPU, Flash Attention, MTP, cuantización KV), guardar configuraciones personalizadas generadas dinámicamente como archivos `.bat` para rápida ejecución, y ver métricas en tiempo real en el chat (tokens/segundo, tokens generados, indicador de ventana de contexto y ventana de razonamiento minimizable).

---

## User Feedback & Requirements Included

1. **Gestor en Python**: El ciclo de vida del servidor `llama-server.exe` y la ejecución de accesos directos será controlado por `cognitivo/gestor_llamacpp.py`.
2. **Navegador / Selector de Carpetas**: Selector dinámico para explorar y definir la carpeta base donde residen los binarios de `llama.cpp` o ejecutables locales.
3. **Generador Dinámico de `.bat`**: En lugar de depender de scripts preexistentes del usuario, la aplicación generará automáticamente archivos `.bat` optimizados en la carpeta del proyecto cada vez que el usuario guarde o modifique un perfil de configuración.
4. **Telemetría Avanzada del Sistema (LM Studio Dashboard)**:
   - Uso y disponibilidad de RAM y CPU.
   - Uso de espacio en Discos (SSD / HDD).
   - Monitoreo de VRAM y Temperatura de GPU / Componentes.
5. **Métricas e Indicadores en el Chat**:
   - Muestra de Tokens generados y Velocidad de Inferencia (**tokens por segundo - t/s**).
   - Indicador de consumo de la **Ventana de Contexto** (ej: `4,096 / 128,000 tokens`).
   - Ventana minimizable/desplegable para el **Razonamiento** del modelo (etiquetas `<think>`).
6. **MTP / Speculative Decoding Slider**:
   - Slider horizontal interactivo con perilla móvil para ajustar `--spec-draft-n-max` entre **1 y 10**.
7. **Soporte de Proveedores**: Integración unificada para `llama.cpp`, `Ollama` y `LM Studio`.

---

## Proposed Changes

### Vision Studio Frontend UI

#### [MODIFY] [useSettingsStore.ts](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/stores/useSettingsStore.ts)
- Ampliar el store con los nuevos parámetros del motor local y métricas:
  - `llamacppFolderPath`: Ruta a la carpeta seleccionada de binarios.
  - `llamacppPreset`: Perfil seleccionado (ej. `Qwen 35B 128K MTP`, `Gemma 4 8K`, `Custom`).
  - `llamacppNgl`: Capas en GPU (`-ngl`).
  - `llamacppContextSize`: Tamaño de ventana de contexto (`-c`).
  - `llamacppKvCache`: Cuantización de KV (`f16`, `q8_0`, `q4_0`).
  - `llamacppFlashAttention`: Booleano (`-fa on/off`).
  - `llamacppMtpEnabled`: Activar/Desactivar MTP (`--spec-type draft-mtp`).
  - `llamacppMtpDraftMax`: Valor entero de 1 a 10 (`--spec-draft-n-max [1-10]`).
  - `llamacppPort` y `llamacppHost`: Puerto (`8080`) y Host (`127.0.0.1`).
  - `customBatPresets`: Lista de configuraciones guardadas para generación automática de `.bat`.
  - `systemTelemetry`: Objeto de telemetría (CPU, RAM, Discos, VRAM, Temp).

#### [NEW] [LlamaCppPanel.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Settings/LlamaCppPanel.tsx)
- Panel estilo LM Studio:
  - **Selector de Carpeta**: Input con botón "Examinar..." para ubicar `llama.cpp`.
  - **Header de Telemetría**: Barras e indicadores en tiempo real de RAM, CPU, SSD/HDD, VRAM y Temperatura.
  - **Generador & Guardado de `.bat`**: Botón "Guardar Perfil y Generar .bat" que crea automáticamente un script optimizado de inicio rápido.
  - **Controles de Inferencia**:
    - Sliders horizontales interactivos para GPU Offload Layers (`-ngl`).
    - Selector numérico/dropdown para Context Size (`-c`).
    - Switches/Toggles para Flash Attention y KV Quantization.
    - **Slider Horizontal con Perilla para MTP Draft Max**: Permite graduar `--spec-draft-n-max` de **1 a 10**.

#### [MODIFY] [SettingsModal.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Settings/SettingsModal.tsx)
- Integrar la sección expandida **Local Engine (Llama.cpp / Ollama / LM Studio)** con acceso directo al nuevo panel.

#### [MODIFY] [SidebarChat.tsx](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/vision_studio/src/components/Sidebar/SidebarChat.tsx)
- Agregar métricas de inferencia al pie de cada mensaje del asistente:
  - Tokens generados y **tokens por segundo (t/s)** calculados dinámicamente.
  - Barra de progreso e indicador numérico de la **Ventana de Contexto** utilizada.
  - Ventana minimizable/desplegable para bloques de **Razonamiento** (`<think>`).

---

### Python Backend / Telemetry & Process Manager

#### [NEW] [gestor_llamacpp.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/cognitivo/gestor_llamacpp.py)
- Módulo Python para gestionar:
  1. `iniciar_servidor_llamacpp(config: dict)`: Lanza `llama-server.exe` con las banderas elegidas (incluyendo `--spec-draft-n-max` del slider MTP).
  2. `generar_script_bat(nombre_perfil: str, config: dict)`: Escribe un archivo `.bat` optimizado en la carpeta `scripts/bats/`.
  3. `obtener_telemetria_sistema()`: Usa `psutil` y `pynvml` (o `nvidia-smi`) para reportar uso de CPU, RAM, espacio libre en Discos (SSD/HDD), VRAM consumida y Temperaturas.
  4. `detener_servidor_llamacpp()`: Apaga el proceso del servidor local de forma limpia.

---

## Verification Plan

### Automated Tests
- Ejecutar `python cognitivo/gestor_llamacpp.py --telemetria` para verificar la captura correcta de CPU, RAM, Discos y GPU/Temperaturas.
- Probar la función de generación de archivos `.bat` automáticos validando la bandera MTP `-spec-draft-n-max`.
### Manual Verification
1. Abrir **Vision Studio** -> Configuración -> Modelos -> Motor Local.
2. Probar el slider horizontal con perilla para MTP Speculative Decoding ajustándolo de 1 a 10.
3. Probar el selector de carpetas para ubicar `llama.cpp`.
4. Ajustar parámetros y hacer clic en **Guardar y Generar .bat**.
5. Iniciar el servidor desde la interfaz y verificar las métricas de Telemetría (RAM, CPU, VRAM, Discos, Temp).
6. Enviar una consulta en el chat y verificar que aparezcan los **tokens/segundo**, el indicador de **Ventana de Contexto** y la pestaña de **Razonamiento**.
