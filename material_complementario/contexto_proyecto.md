# 🧠 Proyecto: Visión OS

**Visión OS** es un Sistema Operativo Cognitivo Neuro-Mimético para un Agente de IA Autónomo. A diferencia de los agentes secuenciales tradicionales, está diseñado como un ecosistema modular de daemons asíncronos distribuidos que se comunican mediante un bus de eventos y están supervisados por un watchdog.

---

## 📂 Estructura Física (Anatomía del Cerebro)

El sistema se organiza mapeando regiones funcionales del cerebro humano a componentes de software específicos:

### 1. Sistemas Vitales (Core)
*   **Tallo Cerebral (`core/main.py`):** El daemon Watchdog principal. Inicia los servicios de forma ordenada, monitorea su estado de ejecución y los reinicia automáticamente si se caen.
*   **Corazón (`core/broker_eventos.py`):** Bus de eventos asíncrono basado en TCP sockets (`asyncio`). Distribuye los mensajes de comunicación inter-modular (denominados "Glóbulos Rojos") y soporta suscripciones con comodines (`*`) y comandos de purga de emergencia.
*   **Amígdala (`core/amigdala.py`):** Módulo de seguridad perimetral. Intercepta los prompts crudos para detectar patrones de inyección o comandos prohibidos (`rm -rf`, `sudo`, etc.) y actúa como el botón de pánico del sistema (limpieza de colas).
*   **Glándula Pineal (`core/glandula_pineal.py`):** Módulo encargado de la gestión de energía y alternancia de estados cognitivos (Ciclos de Día/Vigilia y Noche/Consolidación).

### 2. Procesamiento y Consciencia (Cognitivo)
*   **Lóbulo Frontal (`cognitivo/llm_router.py`):** El "Crazy Router". Evalúa el nivel de esfuerzo que requiere una tarea (`esfuerzo_bajo`, `esfuerzo_medio`, `esfuerzo_alto`), administra las llamadas mediante `LiteLLM`, y gestiona fallbacks automáticos hacia modelos locales si las APIs gratuitas fallan.
*   **Hemisferio Izquierdo (`cognitivo/ejecutor_izquierdo.py`):** Lógica analítica y de procedimientos. Encargado del uso de herramientas MCP y de la ejecución segura de scripts en entornos controlados y aislados mediante **Docker Sandbox**.
*   **Hemisferio Derecho (`cognitivo/contexto_derecho.py`):** Analiza el entorno visual del usuario y las variables de estado afectivo del sistema (`emociones.json`) para proveer un contexto holístico y proactivo.

### 3. Almacenamiento y Archivo (Memoria)
*   **Lóbulo Temporal (`memoria/lancedb_manager.py`):** Motor de base de datos vectorial local (LanceDB). Indexa la información en un formato tridimensional (coordenadas X, Y, Z) utilizando embeddings multilingües densos generados localmente por `BAAI/bge-m3` (1024 dimensiones).
*   **Hipocampo (`memoria/hipocampo.py`):** Filtro asíncrono de consolidación. Escucha el final de los procesos o conversaciones, solicita un resumen conciso en 3 viñetas y 5 tags al Lóbulo Frontal, y guarda el resultado sintetizado en la base de datos para evitar saturación de espacio.
*   **Explorador Tavily (`memoria/explorador_tavily.py`):** Agente de investigación web que utiliza la API de Tavily para buscar información limpia de ruido (anuncios y código sobrante) y resolver vacíos de información.
*   **Cerebelo / Renderizador HDD (`memoria/renderizador_hdd.py`):** Motor de automatización de mantenimiento físico. Administra la migración de archivos al disco duro frío basado en umbrales de capacidad y algoritmos de desalojo.

### 4. Percepción y Sentidos (Sentidos)
*   **Lóbulo Parietal (`sentidos/vision_parietal.py`):** Captura continua de la pantalla activa mediante `mss` a 0.2 FPS. Utiliza algoritmos de diferencia de píxeles (comparaciones de thumbnails 32x32 en Pillow) para transmitir frames al broker únicamente cuando hay un cambio visual notable.
*   **Lóbulo Occipital / Imaginación (`sentidos/imaginacion_occipital.py`):** Se encarga de procesar las habilidades creativas y la generación de imágenes/diagramas mediante flujos dirigidos a la API local de **ComfyUI**.
*   **Sistema Periférico (`sentidos/sistema_periferico.py`):** Servidor FastAPI para recibir webhooks de eventos externos (Telegram, GitHub, etc.) y transformarlos en eventos de entrada para el broker.

---

## 📐 Lógica y Fórmulas del Motor de Memoria

### 1. Estructura Espacial Fractal (Base-3)
La base vectorial no es plana, sino un cubo anidado de 3x3x3 (27 celdas por bloque). Con 4 niveles de profundidad (TB → GB → MB → KB), el total de bloques lógicos es:
$$N(4) = 27^4 = 531,441 \text{ bloques}$$

La ubicación global de cualquier bloque en el nivel de profundidad $n$ se calcula acumulando las coordenadas locales $(x_i, y_i, z_i) \in \{0, 1, 2\}$ pesadas por su nivel de escala:
$$X_{global} = \sum_{i=1}^n x_i \cdot 3^{n-i}$$
$$Y_{global} = \sum_{i=1}^n y_i \cdot 3^{n-i}$$
$$Z_{global} = \sum_{i=1}^n z_i \cdot 3^{n-i}$$

### 2. Distancia Euclidiana Semántica-Física
La distancia espacial entre dos fragmentos de memoria se calcula utilizando la escala física $M$ correspondiente a su nivel de magnitud ($KB = \text{mm}$, $MB = \text{cm}$, $GB = \text{m}$, $TB = \text{km}$):
$$\text{Distancia} = M \cdot \sqrt{(X_{global, 2} - X_{global, 1})^2 + (Y_{global, 2} - Y_{global, 1})^2 + (Z_{global, 2} - Z_{global, 1})^2}$$

*   **Eje X/Y:** Similitud del coseno (Cercanía semántica).
*   **Eje Z:** Temperatura (Frecuencia de consulta y actualización).

---

## 💾 Políticas de Almacenamiento (Hot/Cold Tiering)

Para proteger la capacidad limitada del SSD de 1TB, el Cerebelo ejecuta un daemon de monitoreo de disco en tiempo real (`psutil`) cada 1-3 horas (aprox. 5 veces al día):

1.  **Reciente (Caliente - SSD):** Datos creados hoy (Temperatura $100^\circ\text{C}$ a $50^\circ\text{C}$).
2.  **Usado Recientemente (Tibio - SSD/HDD):** Datos de esta semana. Punteros en LanceDB, archivos pesados migrados.
3.  **Usado (Frío - HDD):** Historial antiguo en HDD de 2TB (Temperatura $49^\circ\text{C}$ a $20^\circ\text{C}$).
4.  **Congelado ( HDD Comprimido > 1 mes):** Los recuerdos inactivos por más de un mes se "renderizan": se pasan por un LLM local para resumirlos al máximo, y los archivos binarios se comprimen antes de su archivado definitivo.
5.  **Desalojo (High-Water Mark):** Si el SSD toca el **85%** de uso, el Cerebelo migra automáticamente los datos ordenados de frío a caliente hacia el HDD hasta bajar el espacio ocupado en el SSD al **60%**.

---

## 🚦 Estado de la Hoja de Ruta (Roadmap)

*   **Fase 0 (Cimientos) & Fase 1 (Pulso y Watchdog):** 🟢 **100% Completado** (requirements, watchdog robusto contra encodings locales, broker TCP socket asíncrono).
*   **Fase 2 (Pensamiento y Amígdala):** 🟢 **100% Completado** (config de enrutador, router LiteLLM, interceptador de inyecciones y botón de pánico en Amígdala).
*   **Fase 3 (Memoria Fractal):** 🟢 **100% Completado** (config tiering, LanceDB manager con embeddings locales BGE-m3 y metadatos espaciales, consolidación en Hipocampo).
*   **Fase 4 (Sentidos y Consciencia):** 🟢 **100% Completado** (hardware interfaces JSON, captura optimizada con comparación de thumbnails Pillow, observador en Hemisferio Derecho, y orquestación general en Watchdog).
*   **Fase 5 (Oído Activo y Ejecución):** 🟢 **100% Completado** (SpeechRecognition + faster-whisper en oido_parietal, ejecutor_izquierdo con pyautogui/subprocess, advertencias visuales y mock).
*   **Fase 6 (Refinamiento Cognitivo y Expansión):** 🟢 **100% Completado** (effort_levels y emotions dinámicos, autodescarga de modelos locales con gestor_modelos_locales, imaginacion_occipital con ComfyUI, sistema_periferico FastAPI y calibrador_audio).
