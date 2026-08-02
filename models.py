"""
Modelos SQLAlchemy: representan las tablas de la base de datos.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from database import Base


class Intento(Base):
    """Un intento de dictado realizado por el usuario."""

    __tablename__ = "intentos"

    id = Column(Integer, primary_key=True, index=True)
    frase_id = Column(Integer, index=True, nullable=False)
    texto_original = Column(String, nullable=False)
    texto_escrito = Column(String, nullable=False)
    categoria = Column(String, index=True, nullable=False)
    dificultad = Column(String, index=True, nullable=True)
    modo = Column(String, index=True, nullable=True)

    precision = Column(Float, nullable=False)  # porcentaje 0-100
    tiempo_segundos = Column(Float, nullable=False)
    palabras_correctas = Column(Integer, default=0)
    palabras_incorrectas = Column(Integer, default=0)
    caracteres_incorrectos = Column(Integer, default=0)
    es_correcto = Column(Boolean, default=False)  # precisión == 100

    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc))
