# Walkthrough: Mapa Cerebral Topográfico con Carriles de Scripts y Pulso de Query

Se ha completado la evolución arquitectónica del módulo de Agentes hacia un **Mapa Cerebral Topográfico Interactivo** con **Carriles de Scripts** y simulación de **Pulso de Query**.

## 🧠 Arquitectura Entregada

```
 [ Query del Usuario (PULSO ELÉCTRICO) ]
                    │
                    ▼
     🧠 LÓBULO FRONTAL (Decisión & Router LLM)
        │                       │
        ├── Carril 1: RAG ──────┼──► 📚 LÓBULO PARIETAL (LanceDB)
        │   (cognitivo/memoria.py)
        │                       │
        ├── Carril 2: Web ──────┼──► 🌐 SENTIDOS (Tavily/Scraper)
        │   (cognitivo/web_search.py)
        │                       │
        └── Carril 3: CLI ──────┴──► 💻 HEMISFERIO IZQ. (Terminal Sandbox)
            (cognitivo/ejecutor_izquierdo.py)
```

## Cambios Realizados

1. **Documentación:**
   - **`material_complementario/plan_red_neuronal_agentes.md`:** Especificación completa del Mapa Cerebral Topográfico, Carriles de Scripts y Pulso de Query.

2. **Componentes Frontend (`vision_studio`):**
   - **`src/components/Agents/AgentsSynapticView.tsx` [NUEVO]:**
     - Visualización topográfica de los 5 Lóbulos Cognitivos (Frontal, Parietal, Hemisferio Izquierdo, Sentidos, Temporal).
     - **Carriles de Scripts en Vivo:** Identificación de scripts en Python/Bash que unen los lóbulos.
     - **Disparador de Pulso de Query:** Animación de pulsos eléctricos viajando por los carriles según la complejidad (*Query Simple Express ⚡* vs *Multilóbulo 🕸️*).
     - **Inspector de Vagones de Información:** Selección de carriles para auditar los payloads transmitidos en tiempo real.
   - **`src/App.tsx` [MODIFICADO]:** Integración a pantalla completa del Mapa Cerebral en la vista de Agentes.
