from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import auth_router, docentes_router
from app.api import evaluaciones_router, web_router
import logging

from app import config
from app.api.errores import registrar_manejadores
from app.infrastructure.db import models
from app.infrastructure.db.database import engine

_errores, _avisos = config.problemas_de_configuracion()
for _aviso in _avisos:
    logging.getLogger("evaldoc").warning(_aviso)
if _errores:
    raise RuntimeError("Configuracion invalida para modo real:\n- " + "\n- ".join(_errores))

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EvalDoc API",
    version="1.0.0",
    description="API de EvalDoc, la plataforma donde los estudiantes de la UMB califican y "
    "comentan a sus docentes de forma anónima. Arquitectura hexagonal (domain, application, "
    "api, infrastructure). Autenticación con código OTP al correo institucional y JWT. "
    "Los comentarios pasan por moderación automática (lista de palabras + Gemini) y la "
    "decisión final la toma un moderador.",
)

registrar_manejadores(app)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "api" / "static"), name="static")
app.include_router(web_router.router)
app.include_router(auth_router.router)
app.include_router(docentes_router.router)
app.include_router(evaluaciones_router.catalogo)
app.include_router(evaluaciones_router.evaluaciones)
app.include_router(evaluaciones_router.reportes)


@app.get("/api", tags=["Health"], summary="Verificar que la API funciona")
def inicio():
    return {"mensaje": "EvalDoc API funcionando", "docs": "/docs"}
