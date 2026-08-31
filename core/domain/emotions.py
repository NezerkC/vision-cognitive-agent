"""
Domain entities for emotional and homeostatic states in Visión OS.
"""

from pydantic import BaseModel, Field


class EmotionalState(BaseModel):
    """
    Biological/affective state simulating agent homeostasis.
    """
    emocion_predominante: str = Field("neutral", description="Current predominant emotion: curioso, analitico, alerta, neutral")
    energia_vital: float = Field(100.0, description="Energy percentage (0-100)")
    nivel_estres: float = Field(10.0, description="Stress factor (0-100)")
    modo_vigilia: bool = Field(True, description="True for awake/active, False for consolidation/sleep")
