# Plan de Arquitectura e Implementación: Mapa Cerebral Sináptico y Carriles de Agentes (Vision OS / Vision Studio)

## Concepto Arquitectónico: Mapa Cerebral Topográfico con Carriles de Scripts

El mapa visual de agentes en **Vision Studio** se estructurará como un **Mapa Cerebral Topográfico Interactivo**, donde el flujo de ejecución no es abstracto sino guiado por los **Carriles de Scripts** y el **Pulso de la Query del Usuario**:

```
 [ Query del Usuario (PULSO ELÉCTRICO) ]
                    │
                    ▼
     🧠 LÓBULO FRONTAL (Decisión & LLM Router)
        │                       │
        ├── Carril 1: RAG ──────┼──► 📚 LÓBULO PARIETAL (LanceDB)
        │   (script_memoria.py) │
        │                       │
        ├── Carril 2: Web ──────┼──► 🌐 SENTIDOS (Tavily/Scraper)
        │   (script_search.py)  │
        │                       │
        └── Carril 3: CLI ──────┴──► 💻 HEMISFERIO IZQ. (Terminal Sandbox)
            (script_ejecutor.py)
```

### Componentes Clave:
1. **El Pulso (Query de Entrada):** Cada consulta enviada por el usuario inicia un **Pulso Luminoso** en el punto de entrada que recorre el cerebro en tiempo real.
2. **Los Carriles (Scripts y Agentes Especializados):**
   - Cada carril representa una vía neuronal física respaldada por un **script en Python/Bash** (`cognitivo/skills/`, `cognitivo/distrito_agentes/`).
   - Muestra el nombre del script, su versión y el estado de salud del agente que lo corre.
3. **Complejidad del Pulso (Respuesta Adaptativa):**
   - **Query Simple (Pulso Directo ⚡):** El pulso viaja por un solo carril de script (baja latencia).
   - **Query Compleja (Propagación Multilóbulo 🕸️):** El pulso se bifurca y viaja a través de múltiples carriles de scripts en paralelo y secuencia.
4. **Vagones de Información (Payloads):** Al hacer clic en cualquier punto del carril, se abre el inspector con los datos exactos transmitidos por el script en ese instante.

---

## Cambios Propuestos

### 1. Frontend IDE (`vision_studio`)
- **`src/components/Agents/AgentsSynapticView.tsx` [NUEVO]:**
  - Renderizado del **Mapa Cerebral Topográfico Completo** con fondo oscuro y silueta anatómica sutil.
  - Representación visual de los 5 Lóbulos principales.
  - **Carriles de Scripts Interactivos:** Vías que unen los lóbulos con identificadores de scripts (`script_memoria.py`, `script_search.py`, `script_terminal.py`).
  - **Simulador de Pulso de Query:** Animación de partículas luminosas viajando por los carriles al enviar una consulta o al hacer clic en "Probar Pulso".
  - Inspector lateral/desplegable del **Vagón de Información** conducido por el carril.

---

## Plan de Verificación

### Pruebas Automatizadas
- `cd vision_studio && npx tsc --noEmit`

### Verificación Manual
- Abrir la sección **Agentes** en `vision_studio`.
- Disparar un **Pulso de Query** y observar el recorrido en tiempo real por los **Carriles de Scripts** a través del **Mapa Cerebral**.
