import json
import logging
import operator
import os
from typing import Annotated, TypedDict

import yaml
from langgraph.graph import END, StateGraph

# Setup logger
logger = logging.getLogger("OrquestadorGraph")

class EstadoAgente(TypedDict):
    input_usuario: str
    ruta_planeada: list[str]
    vagones_informacion: Annotated[list, operator.add]
    respuesta_final: str
    request_id: str
    mock: bool

# Node 1: Planificador
async def nodo_planificador(state: EstadoAgente) -> dict:
    logger.info("--- NODO PLANIFICADOR ---")
    input_usuario = state["input_usuario"]

    ruta = []
    text_lower = input_usuario.lower()

    # Plan stations based on user input content
    if any(k in text_lower for k in ["memoria", "lancedb", "recuerd", "historial", "conversación", "anterior", "guardado", "base de datos"]):
        ruta.append("memoria")

    if any(k in text_lower for k in ["emoción", "emocion", "sentimiento", "estado de ánimo", "alegría", "tristeza", "enojado", "feliz", "actualizar_emocion", "lógico", "creativo"]):
        ruta.append("herramientas")

    if any(k in text_lower for k in [
        "buscar", "internet", "web", "google", "investigar",
        "búsqueda", "busqueda", "qué es", "que es",
        "último", "actual", "noticias", "cómo hacer", "como hacer",
        "documentación", "documentacion", "tutorial",
        "última versión", "ultima version",
        "descargar", "precio", "precios",
    ]):
        ruta.append("web")

    # If no route was planned, default to memoria to keep context updated
    if not ruta:
        ruta.append("memoria")

    logger.info(f"Ruta planificada: {ruta}")
    return {"ruta_planeada": ruta, "vagones_informacion": []}


EMOTIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "emotions.json"
)

def _get_current_emotion() -> str:
    try:
        if os.path.exists(EMOTIONS_PATH):
            with open(EMOTIONS_PATH, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("estado", "neutral")
    except Exception:
        pass
    return "neutral"

# Node 2: Memoria (LanceDB Query via LLMRouter)
async def nodo_memoria(state: EstadoAgente) -> dict:
    logger.info("--- NODO MEMORIA ---")
    input_usuario = state["input_usuario"]
    mock = state.get("mock", False)
    request_id = state.get("request_id", "default")
    ruta = state.get("ruta_planeada", [])
    nueva_ruta = ruta[1:] if len(ruta) > 0 else []

    if mock:
        return {
            "vagones_informacion": [{"estacion": "memoria", "resultado": "Mock database memory context for: " + input_usuario}],
            "ruta_planeada": nueva_ruta
        }

    from llm_router import _global_router
    if _global_router is not None:
        current_emotion = _get_current_emotion()
        logger.info(f"Querying memory semantic search for: '{input_usuario}' with emotion_filter='{current_emotion}'")

        # Modify the query or use metadata filtering in the router
        results = await _global_router.perform_memory_search(request_id, input_usuario, emotion_filter=current_emotion)
        formatted_results = []
        if results:
            for r in results:
                formatted_results.append({
                    "fichero": r.get('metadata', {}).get('filename', 'desconocido'),
                    "texto": r.get('text', ''),
                    "score": r.get('score', 1.0)
                })
        return {
            "vagones_informacion": [{"estacion": "memoria", "resultado": formatted_results}],
            "ruta_planeada": nueva_ruta
        }

    return {
        "vagones_informacion": [{"estacion": "memoria", "resultado": "No database search engine active."}],
        "ruta_planeada": nueva_ruta
    }

# Node 3: Herramientas (executes tools like emotional updates)
async def nodo_herramientas(state: EstadoAgente) -> dict:
    logger.info("--- NODO HERRAMIENTAS ---")
    input_usuario = state["input_usuario"]
    mock = state.get("mock", False)
    ruta = state.get("ruta_planeada", [])
    nueva_ruta = ruta[1:] if len(ruta) > 0 else []

    # Extract emotion update parameters using LLM Router
    if mock:
        return {
            "vagones_informacion": [{"estacion": "herramientas", "resultado": "Mock tool execution completed."}],
            "ruta_planeada": nueva_ruta
        }

    from llm_router import enrutar_peticion
    from skills.sistema_emocional import actualizar_emocion

    extraction_prompt = (
        "Analiza el mensaje del usuario y extrae los parámetros para actualizar la emoción del sistema.\n"
        f"Mensaje del usuario: \"{input_usuario}\"\n\n"
        "Debes responder EXCLUSIVAMENTE con un JSON válido con esta estructura (sin bloques de código markdown ni texto adicional):\n"
        "{\n"
        "  \"estado\": \"neutral\" | \"alegría\" | \"tristeza\" | \"enojo\" | \"intriga\" | \"lógico\" | \"creativo\",\n"
        "  \"intensidad\": float (entre 0.0 y 1.0)\n"
        "}"
    )

    try:
        response = await enrutar_peticion(extraction_prompt, esfuerzo="esfuerzo_bajo")
        clean_str = response.strip()
        if clean_str.startswith("```json"):
            clean_str = clean_str[7:]
        if clean_str.endswith("```"):
            clean_str = clean_str[:-3]
        clean_str = clean_str.strip()

        params = json.loads(clean_str)
        estado = params.get("estado", "neutral")
        intensidad = float(params.get("intensidad", 0.5))

        # Call tool
        tool_result = actualizar_emocion.invoke({"estado": estado, "intensidad": intensidad})
        return {
            "vagones_informacion": [{"estacion": "herramientas", "resultado": tool_result}],
            "ruta_planeada": nueva_ruta
        }
    except Exception as e:
        logger.error(f"Failed to execute tools in graph: {e}")
        return {
            "vagones_informacion": [{"estacion": "herramientas", "resultado": f"Tool error: {str(e)}"}],
            "ruta_planeada": nueva_ruta
        }

# Node 4: Web search (internet lookup via DuckDuckGo/Tavily)
async def nodo_web(state: EstadoAgente) -> dict:
    logger.info("--- NODO WEB ---")
    input_usuario = state["input_usuario"]
    mock = state.get("mock", False)
    ruta = state.get("ruta_planeada", [])
    nueva_ruta = ruta[1:] if len(ruta) > 0 else []

    if mock:
        return {
            "vagones_informacion": [{
                "estacion": "web",
                "resultado": {
                    "status": "success",
                    "source": "mock",
                    "results": [{"title": "Resultado simulado", "url": "", "snippet": f"Simulated web search for: {input_usuario}"}]
                }
            }],
            "ruta_planeada": nueva_ruta
        }

    try:
        from skills.websearch_tool import buscar_en_web_func
        results_json = await buscar_en_web_func(query=input_usuario, max_results=5)
        import json
        results = json.loads(results_json)
        logger.info(f"Web search returned {len(results.get('results', []))} results")
        return {
            "vagones_informacion": [{"estacion": "web", "resultado": results}],
            "ruta_planeada": nueva_ruta
        }
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return {
            "vagones_informacion": [{"estacion": "web", "resultado": {"status": "error", "error": str(e), "results": []}}],
            "ruta_planeada": nueva_ruta
        }

# Node 5: Respuesta (Synthesizes final answer)
async def nodo_respuesta(state: EstadoAgente) -> dict:
    logger.info("--- NODO RESPUESTA ---")
    input_usuario = state["input_usuario"]
    mock = state.get("mock", False)
    vagones = state.get("vagones_informacion", [])

    # Load personality configuration
    personality_prompt = "Eres Visión, un co-ingeniero autónomo de Visión OS."
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pers_path = os.path.join(project_root, "config", "personalidad.yaml")

    if os.path.exists(pers_path):
        try:
            with open(pers_path, encoding="utf-8") as f:
                p_data = yaml.safe_load(f)
            personality_prompt = p_data.get("identidad", {}).get("prompt", personality_prompt)
        except Exception as e:
            logger.warning(f"Could not load personality: {e}")

    # Load emotional state
    emotions_str = "Neutral"
    emotions_path = os.path.join(project_root, "config", "emotions.json")
    if os.path.exists(emotions_path):
        try:
            with open(emotions_path, encoding="utf-8") as f:
                e_data = json.load(f)
            emotions_str = f"{e_data.get('estado', 'neutral').capitalize()} (Intensidad: {e_data.get('intensidad', 1.0)})"
        except Exception:
            pass

    # Compile gathered context from vagones_informacion
    context_str = ""
    for v in vagones:
        est = v.get("estacion", "desconocida").upper()
        res = v.get("resultado", "")
        context_str += f"\n--- ESTACIÓN: {est} ---\n{json.dumps(res, indent=2, ensure_ascii=False)}\n"

    # Call LLM for final response synthesis
    if mock:
        return {"respuesta_final": f"Mock response for: {input_usuario} [State: {emotions_str}]"}

    from llm_router import enrutar_peticion

    synthesis_prompt = (
        f"{personality_prompt}\n\n"
        f"Estado Emocional Actual: {emotions_str}\n"
        f"Datos e Información recolectados por los Lóbulos de Visión OS:\n{context_str}\n\n"
        f"Pregunta del Arquitecto: \"{input_usuario}\"\n\n"
        "Genera tu respuesta final de ingeniería colaborativa en base a los datos recolectados. Responde directamente en español."
    )

    try:
        final_answer = await enrutar_peticion(synthesis_prompt, esfuerzo="esfuerzo_medio")
        return {"respuesta_final": final_answer}
    except Exception as e:
        return {"respuesta_final": f"Error al sintetizar respuesta: {str(e)}"}

# Conditional routing edge
def enrutador_estaciones(state: EstadoAgente):
    ruta = state.get("ruta_planeada", [])
    if not ruta:
        return "nodo_respuesta"

    # Pick next station
    next_station = ruta[0]

    if next_station == "memoria":
        return "nodo_memoria"
    elif next_station == "web":
        return "nodo_web"
    elif next_station == "herramientas":
        return "nodo_herramientas"
    else:
        return "nodo_respuesta"

# Build the StateGraph
workflow = StateGraph(EstadoAgente)

workflow.add_node("nodo_planificador", nodo_planificador)
workflow.add_node("nodo_memoria", nodo_memoria)
workflow.add_node("nodo_web", nodo_web)
workflow.add_node("nodo_herramientas", nodo_herramientas)
workflow.add_node("nodo_respuesta", nodo_respuesta)

workflow.set_entry_point("nodo_planificador")

# Connect nodes through conditional routing
workflow.add_conditional_edges(
    "nodo_planificador",
    enrutador_estaciones,
    {
        "nodo_memoria": "nodo_memoria",
        "nodo_web": "nodo_web",
        "nodo_herramientas": "nodo_herramientas",
        "nodo_respuesta": "nodo_respuesta"
    }
)

workflow.add_conditional_edges(
    "nodo_memoria",
    enrutador_estaciones,
    {
        "nodo_memoria": "nodo_memoria",
        "nodo_web": "nodo_web",
        "nodo_herramientas": "nodo_herramientas",
        "nodo_respuesta": "nodo_respuesta"
    }
)

workflow.add_conditional_edges(
    "nodo_web",
    enrutador_estaciones,
    {
        "nodo_memoria": "nodo_memoria",
        "nodo_web": "nodo_web",
        "nodo_herramientas": "nodo_herramientas",
        "nodo_respuesta": "nodo_respuesta"
    }
)

workflow.add_conditional_edges(
    "nodo_herramientas",
    enrutador_estaciones,
    {
        "nodo_memoria": "nodo_memoria",
        "nodo_web": "nodo_web",
        "nodo_herramientas": "nodo_herramientas",
        "nodo_respuesta": "nodo_respuesta"
    }
)

workflow.add_edge("nodo_respuesta", END)

orquestador_graph = workflow.compile()

async def ejecutar_orquestador_graph(input_usuario: str, request_id: str, mock: bool = False) -> str:
    """
    Executes the compiled StateGraph with the given input and returns the final answer.
    """
    initial_state = {
        "input_usuario": input_usuario,
        "ruta_planeada": [],
        "vagones_informacion": [],
        "respuesta_final": "",
        "request_id": request_id,
        "mock": mock
    }
    try:
        final_state = await orquestador_graph.ainvoke(initial_state)
        return final_state.get("respuesta_final", "Error: No se produjo respuesta final.")
    except Exception as e:
        logger.error(f"Error executing StateGraph: {e}")
        return f"Error en el núcleo cognitivo de grafo: {str(e)}"
