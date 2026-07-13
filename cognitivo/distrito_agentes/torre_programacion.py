"""
torre_programacion.py — Edificio Multiagente para generación y revisión de código.

Usa LangGraph para crear un ciclo de 3 agentes (Arquitecto → Programador → QA)
que se pasan el trabajo hasta que el código pasa la revisión de calidad.

Dependencia: pip install langgraph
"""

from __future__ import annotations

import logging
import sys
from typing import Any

# ─────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] TorreProg: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TorreProgramacion")


# ─────────────────────────────────────────────────────────────────
# 1. Definición del Estado
# ─────────────────────────────────────────────────────────────────
try:
    from typing import TypedDict, Annotated, List
    from langgraph.graph import StateGraph, END
    LANGRAPH_DISPONIBLE = True
except ImportError:
    LANGRAPH_DISPONIBLE = False
    logger.warning(
        "⚠️ langgraph no está instalado. La torre no funcionará hasta que corras:\n"
        "   pip install langgraph"
    )
    # Placeholder types para que el archivo se pueda importar sin error
    TypedDict = dict
    StateGraph = object
    END = "END"


class EstadoEdificio(TypedDict):
    """Documentos que se pasan de escritorio en escritorio."""
    peticion_usuario: str
    plan_arquitectura: str
    codigo_generado: str
    errores_encontrados: list[str]
    iteraciones: int


# ─────────────────────────────────────────────────────────────────
# 2. Los Agentes (Empleados del Edificio)
# ─────────────────────────────────────────────────────────────────
async def agente_arquitecto(state: EstadoEdificio) -> dict:
    """Diseña la estructura del software."""
    from cognitivo.llm_router import enrutar_peticion

    logger.info("👨‍💼 [Arquitecto] Diseñando la estructura del software...")
    prompt = (
        "Eres un arquitecto de software senior. Dada la siguiente petición del usuario, "
        "creá un plan técnico paso a paso detallado que un programador pueda seguir "
        "para implementar la solución. Incluí estructura de archivos, componentes, "
        "y lógica principal.\n\n"
        f"Petición: {state['peticion_usuario']}"
    )
    plan = await enrutar_peticion(prompt, esfuerzo="esfuerzo_medio")
    logger.info(f"📐 Plan generado ({len(plan)} chars)")
    return {"plan_arquitectura": plan}


async def agente_programador(state: EstadoEdificio) -> dict:
    """Escribe el código basándose en el plan."""
    from cognitivo.llm_router import enrutar_peticion

    errores_previos = state.get("errores_encontrados", [])
    errores_texto = "\n".join(errores_previos) if errores_previos else "Ninguno por ahora."

    logger.info("👨‍💻 [Programador] Escribiendo el código...")
    prompt = (
        "Eres un programador experto. Implementá el código SIGUIENDO ESTRICTAMENTE el plan de arquitectura.\n\n"
        f"## Plan de Arquitectura\n{state['plan_arquitectura']}\n\n"
        f"## Errores de iteraciones anteriores a EVITAR\n{errores_texto}\n\n"
        "IMPORTANTE: Devolvé SOLO el código completo y funcional, sin explicaciones adicionales."
    )
    codigo = await enrutar_peticion(prompt, esfuerzo="esfuerzo_alto")
    logger.info(f"💻 Código generado ({len(codigo)} chars, iteración {state.get('iteraciones', 0) + 1})")
    return {
        "codigo_generado": codigo,
        "iteraciones": state.get("iteraciones", 0) + 1
    }


async def agente_qa(state: EstadoEdificio) -> dict:
    """Revisa el código en busca de bugs."""
    from cognitivo.llm_router import enrutar_peticion

    logger.info("🕵️‍♂️ [QA Tester] Revisando el código en busca de bugs...")
    prompt = (
        "Sos un revisor de código estricto. Analizá el siguiente código y buscá:\n"
        "- Errores de sintaxis\n"
        "- Bugs lógicos\n"
        "- Malas prácticas\n"
        "- Problemas de seguridad\n\n"
        f"Código:\n```\n{state['codigo_generado']}\n```\n\n"
        "Respondé EXCLUSIVAMENTE con 'APROBADO' si el código es correcto, "
        "o con una lista numerada de los errores encontrados si hay problemas."
    )
    revision = await enrutar_peticion(prompt, esfuerzo="esfuerzo_bajo")

    if "APROBADO" in revision.upper() and len(revision) < 30:
        errores: list[str] = []
        logger.info("✅ QA: Código APROBADO")
    else:
        errores = [revision]
        logger.warning(f"❌ QA: {len(errores)} error(es) encontrado(s)")

    return {"errores_encontrados": errores}


# ─────────────────────────────────────────────────────────────────
# 3. Inspector de Calidad (Condición de salida)
# ─────────────────────────────────────────────────────────────────
def inspector_de_calidad(state: EstadoEdificio) -> str:
    """Decide si el código está listo o hay que rehacerlo."""
    errores = state.get("errores_encontrados", [])
    iteraciones = state.get("iteraciones", 0)

    if not errores or iteraciones >= 3:
        logger.info(
            f"✅ [Inspector] Código {'aprobado' if not errores else 'límite alcanzado'} "
            f"({iteraciones} iteraciones). Saliendo del edificio."
        )
        return "fin"
    else:
        logger.info(f"❌ [Inspector] Código rechazado. Iteración {iteraciones}/3. Devolviendo al Programador.")
        return "corregir"


# ─────────────────────────────────────────────────────────────────
# 4. Construcción del Grafo
# ─────────────────────────────────────────────────────────────────
def construir_torre_programacion():
    """
    Crea el grafo LangGraph con el flujo:
      Arquitecto → Programador → QA → ¿Errores? → Programador (loop) o END
    """
    if not LANGRAPH_DISPONIBLE:
        raise ImportError(
            "LangGraph no está instalado. Corré: pip install langgraph"
        )

    constructor = StateGraph(EstadoEdificio)

    # Escritorios
    constructor.add_node("Arquitecto", agente_arquitecto)
    constructor.add_node("Programador", agente_programador)
    constructor.add_node("QA", agente_qa)

    # Pasillos
    constructor.set_entry_point("Arquitecto")
    constructor.add_edge("Arquitecto", "Programador")
    constructor.add_edge("Programador", "QA")

    # Bucle de retroalimentación
    constructor.add_conditional_edges(
        "QA",
        inspector_de_calidad,
        {
            "corregir": "Programador",
            "fin": END,
        }
    )

    return constructor.compile()


# ─────────────────────────────────────────────────────────────────
# 5. API Pública
# ─────────────────────────────────────────────────────────────────
async def ejecutar_peticion_codigo(peticion: str) -> str:
    """
    Procesa una petición de código a través de toda la torre multiagente.

    Args:
        peticion: Descripción del código a generar.

    Returns:
        El código final generado después de pasar por QA.
    """
    if not LANGRAPH_DISPONIBLE:
        return (
            "⚠️ La Torre de Programación requiere LangGraph.\n"
            "Instalalo con: pip install langgraph"
        )

    torre = construir_torre_programacion()
    estado_inicial: EstadoEdificio = {
        "peticion_usuario": peticion,
        "plan_arquitectura": "",
        "codigo_generado": "",
        "errores_encontrados": [],
        "iteraciones": 0,
    }

    logger.info(f"\n🏢 Entrando a la Torre de Programación con: '{peticion}'")
    resultado_final = await torre.ainvoke(estado_inicial)

    codigo = resultado_final.get("codigo_generado", "")
    logger.info(f"🏁 Torre completada. Código generado ({len(codigo)} chars).")
    return codigo


# ─────────────────────────────────────────────────────────────────
# 6. Uso directo (prueba)
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio

    async def demo():
        codigo = await ejecutar_peticion_codigo(
            "Hacé una función en Python que dado un array de números, "
            "devuelva los que son primos."
        )
        print("\n" + "=" * 60)
        print("CÓDIGO GENERADO:")
        print(codigo)

    asyncio.run(demo())
