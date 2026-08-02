"""
API REST para la aplicación de entrenamiento de escucha y escritura (dictado).

Ejecutar en desarrollo:
    uvicorn main:app --reload --port 8000
"""
import json
import random
import os
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import models
import schemas
from database import Base, SessionLocal, engine, get_db

BASE_DIR = Path(__file__).resolve().parent
FRASES_PATH = BASE_DIR / "frases.json"
AUDIOS_DIR = BASE_DIR / "audios"
AUDIOS_DIR.mkdir(exist_ok=True)

# Crea las tablas si no existen.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Dictado Interactivo API",
    description="API para entrenar velocidad de escucha y escritura",
    version="1.0.0",
)
load_dotenv()
# Definimos el nombre de la cabecera HTTP que el cliente debe enviar
API_KEY_NAME = "X-API-Key"

API_KEY_SECRETA = os.getenv("API_KEY_SECRETA")

# Configuramos el esquema de seguridad por cabecera
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def verificar_api_key(api_key: str = Security(api_key_header)):
    """Función de dependencia para validar la API Key."""
    if api_key != API_KEY_SECRETA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado: API Key inválida o faltante",
        )
    return api_key

# CORS abierto para desarrollo local del frontend (Vite en :5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sirve los MP3 en /audios/<archivo>.mp3
app.mount("/audios", StaticFiles(directory=str(AUDIOS_DIR)), name="audios")


# --------------------------------------------------------------------------
# Carga de frases en memoria
# --------------------------------------------------------------------------
def cargar_frases() -> List[dict]:
    if not FRASES_PATH.exists():
        return []
    with open(FRASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


FRASES: List[dict] = cargar_frases()
CATEGORIAS_VALIDAS = sorted({f["categoria"] for f in FRASES}) or [
    "palabras",
    "frases",
    "direcciones",
    "numeros",
    "911",
]


def frase_a_schema(frase: dict, request: Request) -> schemas.Frase:
    """Convierte una entrada del JSON en un schema de salida con URL absoluta del audio."""
    base_url = str(request.base_url).rstrip("/")
    return schemas.Frase(
        id=frase["id"],
        texto=frase["texto"],
        audio=f"{base_url}/audios/{frase['audio']}",
        categoria=frase["categoria"],
        dificultad=frase.get("dificultad", "media"),
        duracion=frase.get("duracion", 0.0),
        permite_repetir=frase.get("permite_repetir", True),
        etiquetas=frase.get("etiquetas", []),
    )


# --------------------------------------------------------------------------
# Endpoints de frases (Protegidos con dependencies=[Depends(verificar_api_key)])
# --------------------------------------------------------------------------
@app.get("/frase/random", response_model=schemas.Frase, tags=["frases"], dependencies=[Depends(verificar_api_key)])
def obtener_frase_random(
    request: Request,
    categoria: Optional[str] = Query(
        None, description="palabras | frases | direcciones | numeros | 911"
    ),
    dificultad: Optional[str] = Query(None, description="facil | media | dificil"),
):
    """Devuelve una frase aleatoria, opcionalmente filtrada por categoría y dificultad."""
    candidatas = FRASES

    if categoria and categoria != "aleatorio":
        candidatas = [f for f in candidatas if f["categoria"] == categoria]

    if dificultad:
        candidatas = [f for f in candidatas if f.get("dificultad") == dificultad]

    if not candidatas:
        raise HTTPException(
            status_code=404,
            detail="No hay frases disponibles para los filtros indicados.",
        )

    frase = random.choice(candidatas)
    return frase_a_schema(frase, request)


@app.get("/frases", response_model=List[schemas.Frase], tags=["frases"], dependencies=[Depends(verificar_api_key)])
def listar_frases(
    request: Request,
    categoria: Optional[str] = None,
    dificultad: Optional[str] = None,
):
    """Lista todas las frases disponibles (útil para depuración / administración)."""
    candidatas = FRASES
    if categoria:
        candidatas = [f for f in candidatas if f["categoria"] == categoria]
    if dificultad:
        candidatas = [f for f in candidatas if f.get("dificultad") == dificultad]
    return [frase_a_schema(f, request) for f in candidatas]


@app.get("/categorias", tags=["frases"], dependencies=[Depends(verificar_api_key)])
def listar_categorias():
    """Devuelve las categorías disponibles según el contenido de frases.json."""
    return {"categorias": CATEGORIAS_VALIDAS}


# --------------------------------------------------------------------------
# Endpoints de intentos / estadísticas (Protegidos)
# --------------------------------------------------------------------------
@app.post("/intento", response_model=schemas.IntentoOut, tags=["intentos"], dependencies=[Depends(verificar_api_key)])
def guardar_intento(intento: schemas.IntentoCreate, db: Session = Depends(get_db)):
    """Guarda el resultado de un intento de dictado en la base de datos."""
    nuevo = models.Intento(**intento.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@app.get("/historial", response_model=List[schemas.IntentoOut], tags=["intentos"], dependencies=[Depends(verificar_api_key)])
def obtener_historial(
    limite: int = Query(20, ge=1, le=200),
    categoria: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Devuelve los últimos intentos, más recientes primero."""
    query = db.query(models.Intento)
    if categoria:
        query = query.filter(models.Intento.categoria == categoria)
    return query.order_by(models.Intento.fecha.desc()).limit(limite).all()


@app.get(
    "/estadisticas", response_model=schemas.EstadisticasGenerales, tags=["intentos"], dependencies=[Depends(verificar_api_key)]
)
def obtener_estadisticas(db: Session = Depends(get_db)):
    """Calcula estadísticas generales y por categoría, incluida la racha de aciertos."""
    total = db.query(func.count(models.Intento.id)).scalar() or 0
    precision_promedio = db.query(func.avg(models.Intento.precision)).scalar() or 0.0

    por_categoria = []
    filas = (
        db.query(
            models.Intento.categoria,
            func.count(models.Intento.id),
            func.avg(models.Intento.precision),
            func.avg(models.Intento.tiempo_segundos),
            func.max(models.Intento.precision),
        )
        .group_by(models.Intento.categoria)
        .all()
    )
    for cat, cnt, prom, tiempo_prom, mejor in filas:
        por_categoria.append(
            schemas.EstadisticaCategoria(
                categoria=cat,
                total_intentos=cnt,
                precision_promedio=round(prom or 0.0, 1),
                tiempo_promedio=round(tiempo_prom or 0.0, 1),
                mejor_precision=round(mejor or 0.0, 1),
            )
        )

    # Racha: se recorre el historial completo en orden cronológico.
    todos = (
        db.query(models.Intento.es_correcto)
        .order_by(models.Intento.fecha.asc())
        .all()
    )
    racha_actual = 0
    mejor_racha = 0
    for (correcto,) in todos:
        if correcto:
            racha_actual += 1
            mejor_racha = max(mejor_racha, racha_actual)
        else:
            racha_actual = 0

    return schemas.EstadisticasGenerales(
        total_intentos=total,
        precision_promedio=round(precision_promedio, 1),
        racha_actual=racha_actual,
        mejor_racha=mejor_racha,
        por_categoria=por_categoria,
    )


@app.get("/", tags=["root"])
def raiz():
    """Endpoint raíz mantenido público para comprobar estado de la API."""
    return {"mensaje": "Dictado Interactivo API", "frases_cargadas": len(FRASES)}