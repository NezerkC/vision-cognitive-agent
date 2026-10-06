# 🏛️ Plan de Implementación: Arquitectura Hexagonal y Robusta — Visión OS

## 1. Visión General y Objetivos
Migrar Visión OS desde una arquitectura fragmentada de 14 procesos con sockets TCP artesanales hacia una **Arquitectura Hexagonal (Ports & Adapters)** modular, resiliente, segura y de alto rendimiento.

### Objetivos Clave:
1. **Unificación de Runtime:** Reducir los 14 subprocesos de Python a un único orquestador asíncrono supervisado (`asyncio.TaskGroup`), reduciendo la huella de RAM de >4.5 GB a <850 MB y el tiempo de arranque de 18s a <1s.
2. **Bus de Eventos Resiliente:** Crear `AsyncInMemoryEventBus` con colas independientes por suscriptor, backpressure y bridge TCP opcional para clientes externos.
3. **Pipeline Multimodal Confiable:** Reparar la Amígdala y el LLMRouter para preservar y enrutar imágenes base64 sin amputación de datos.
4. **Optimización de Embeddings y Vector Store:** Centralizar el acceso a LanceDB, calcular embeddings una sola vez por consulta y preparar soporte para FastEmbed/ONNX.
5. **Percepción Inteligente (Trigger de 3 Fases):** Eliminar el polling ciego de visión cada 5s para ahorrar millones de tokens diarios.
6. **Seguridad y Aislamiento:** Validar comandos y scripts generados dinámicamente con AST y políticas de ejecución segura.

---

## 2. Estructura de Paquetes y Capas Hexagonales

```
core/
├── domain/                  # Entidades puras y objetos de valor
│   ├── __init__.py
│   ├── events.py            # EventEnvelope, payloads tipados con Pydantic v2
│   ├── memory_entities.py   # MemoryRecord, Coordinates4D, StorageTier
│   └── emotions.py          # EmotionState, CognitiveStatus
├── ports/                   # Interfaces abstractas (Protocol / ABC)
│   ├── __init__.py
│   ├── event_bus.py         # IEventBus
│   ├── memory_repo.py       # IMemoryRepository
│   ├── llm_gateway.py       # ILLMGateway
│   ├── safety_guard.py      # ISafetyGuard
│   └── senses.py            # ISensoryInput, ISensoryOutput
├── adapters/                # Implementaciones concretas de puertos
│   ├── __init__.py
│   ├── event_bus_inmemory.py # AsyncInMemoryEventBus de alta velocidad
│   ├── event_bus_tcp_bridge.py # Bridge TCP para compatibilidad externa
│   ├── lancedb_adapter.py   # Implementación de IMemoryRepository
│   ├── litellm_adapter.py   # Implementación de ILLMGateway con Circuit Breaker
│   └── amigdala_adapter.py  # Implementación de ISafetyGuard
├── services/                # Casos de uso y daemons orquestados
│   ├── __init__.py
│   ├── sensory_service.py   # Coordinación de visión, oído y habla
│   ├── cognitive_service.py # Coordinación de router, grafo e intriga
│   └── memory_service.py    # Consolidación vigilia/sueño y GraphRAG
├── orchestrator.py          # Unified Brainstem Supervisor (TaskGroup)
└── main.py                  # Entrypoint principal unificado
```

---

## 3. Fases de Ejecución

### Fase 1: Dominio y Puertos (`core/domain/` y `core/ports/`)
- Definir contratos formales con `pydantic.BaseModel` y `typing.Protocol`.
- Establecer esquemas inmutables para todos los mensajes del sistema.

### Fase 2: Adaptador de Bus de Eventos en Memoria (`core/adapters/event_bus_inmemory.py`)
- Implementar bus de eventos in-process con `asyncio.Queue` por suscriptor.
- Implementar soporte para suscripciones jerárquicas y wildcards (`canal.*`).
- Añadir bridge TCP opcional en el puerto 5000 para herramientas externas.

### Fase 3: Adaptadores de Memoria, LLM y Seguridad
- Adaptar `lancedb_manager.py` como `LanceDBAdapter` con cache de embedding en búsquedas progresivas.
- Adaptar `amigdala.py` para preservar payloads multimodales (`image_base64`).
- Adaptar `llm_router.py` con Circuit Breaker ante caídas de proveedores.

### Fase 4: Servicios Sensoriales y Cognitivos Unificados
- Corregir bug del stream de audio en `oido_parietal.py`.
- Corregir el timeout de 60s en bucles sensoriales.
- Implementar trigger visual en `vision_parietal.py`.

### Fase 5: Orquestador Central Monoproceso (`core/orchestrator.py` y `core/main.py`)
- Crear `UnifiedBrainstemOrchestrator` que ejecuta todos los servicios como tareas asíncronas en un solo proceso.
- Unificar scripts de arranque (`start_all.py` / `start_all.bat`).

### Fase 6: Testing Integral y Validación
- Suite completa de tests unitarios y de integración.
- Verificación con Ruff y Pytest.
