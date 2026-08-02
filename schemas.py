"""
Esquemas Pydantic para validar entradas y salidas de la API.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class Frase(BaseModel):
    id: int
    texto: str
    audio: str  # URL completa una vez procesada por la API
    categoria: str
    dificultad: str = "media"
    duracion: float = 0.0
    permite_repetir: bool = True
    etiquetas: List[str] = Field(default_factory=list)


class IntentoCreate(BaseModel):
    frase_id: int
    texto_original: str
    texto_escrito: str
    categoria: str
    dificultad: Optional[str] = None
    modo: Optional[str] = None
    precision: float
    tiempo_segundos: float
    palabras_correctas: int = 0
    palabras_incorrectas: int = 0
    caracteres_incorrectos: int = 0
    es_correcto: bool = False


class IntentoOut(IntentoCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: datetime


class EstadisticaCategoria(BaseModel):
    categoria: str
    total_intentos: int
    precision_promedio: float
    tiempo_promedio: float
    mejor_precision: float


class EstadisticasGenerales(BaseModel):
    total_intentos: int
    precision_promedio: float
    racha_actual: int
    mejor_racha: int
    por_categoria: List[EstadisticaCategoria]
