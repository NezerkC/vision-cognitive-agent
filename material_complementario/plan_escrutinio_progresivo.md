# Implementation Plan - Algoritmo de Escrutinio Progresivo en LanceDBManager

Implementación del algoritmo de búsqueda adaptativa de escrutinio progresivo en `memoria/lancedb_manager.py` y creación de suite de pruebas unitarias en `tests/unit/test_escrutinio_progresivo.py` bajo el alcance `feat/escrutinio-progresivo`.

## User Review Required

> [!IMPORTANT]
> El algoritmo de escrutinio progresivo relaja dinámicamente los parámetros de búsqueda (`top_k` y `umbral_similitud`) cada 3 intentos hasta un máximo de 10 iteraciones si no se obtienen resultados suficientes con el umbral estricto inicial. Si al agotar los 10 intentos no hay coincidencias aceptables, se activa un fallback seguro sin alucinaciones.

## Open Questions

Ninguna por el momento. Las reglas de incremento (`top_k += 2`) y decremento (`umbral -= 0.05` cada 3 intentos) siguen la especificación del sistema.

---

## Proposed Changes

### Memoria Tiering / LanceDB Manager

#### [MODIFY] [lancedb_manager.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/memoria/lancedb_manager.py)

- Agregar el método `buscar_con_escrutinio_progresivo()` a `LanceDBManager`:
  - Firma: `async def buscar_con_escrutinio_progresivo(self, query: str, top_k_inicial: int = 3, umbral_similitud_inicial: float = 0.7, max_intentos: int = 10, paso_adaptativo: int = 3, emotion_filter: str | None = None) -> dict`
  - Bucle de búsqueda adaptativa (hasta 10 intentos):
    - Ejecuta `buscar_hibrido_rrf_impl` con el `top_k` y filtro vigentes.
    - Filtra los resultados cuyo score sea mayor o igual al `umbral_similitud` actual.
    - Si se hallan resultados válidos, retorna diccionario con resultados y objeto de telemetría (`intentos_realizados`, `top_k_final`, `umbral_final`, `exito: True`).
    - Si `intento % paso_adaptativo == 0`: incrementa `top_k` (`+2`) y decrementa `umbral_similitud` (`-0.05`).
  - Fallback sin alucinaciones si se alcanzan los `max_intentos` sin superar el umbral: retorna `{"resultados": [], "telemetria": {"intentos": max_intentos, "exito": False, "motivo": "Sin coincidencias dentro del margen de confianza"}}` o los resultados con mayor puntaje marcado como fallback.
- Actualizar `handle_buscar()` para admitir las peticiones con escrutinio progresivo (`action: "buscar_escrutinio"` o flag `escrutinio: True`).

---

### Unit Tests

#### [NEW] [test_escrutinio_progresivo.py](file:///c:/Users/lolpl/Desktop/02_Proyectos_Dev/vision-cognitive-agent/tests/unit/test_escrutinio_progresivo.py)

- Crear suite Pytest para validar:
  1. Coincidencia directa de alta precisión (éxito en intento 1).
  2. Relajación adaptativa progresiva (éxito tras N incrementos/decrementos).
  3. Fallback seguro tras 10 intentos fallidos sin alucinaciones.
  4. Retorno correcto de estructura de telemetría.

---

## Verification Plan

### Automated Tests
- `pytest tests/unit/test_escrutinio_progresivo.py`
- `pytest tests/`
- `ruff check core/ cognitivo/ sentidos/ memoria/ tests/`

### Manual Verification
- Verificación del comportamiento del evento `canal.memoria` simulando consultas con mock embedder.
