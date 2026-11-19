from functools import lru_cache

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import config
from app.application.cuenta_service import CuentaService
from app.application.docente_service import CatalogoService, DocenteService
from app.application.evaluacion_service import EvaluacionService, ReporteService
from app.application.moderacion_service import ModeracionService, ModeradorIA, ModeradorPalabras
from app.infrastructure.db.database import get_db
from app.domain.exceptions import SinPermiso
from app.infrastructure.db.sqlalchemy_docente_repository import (
    SqlAlchemyCatalogoRepository,
    SqlAlchemyDocenteRepository,
)
from app.infrastructure.db.sqlalchemy_evaluacion_repository import (
    SqlAlchemyEvaluacionRepository,
    SqlAlchemyReporteRepository,
)
from app.infrastructure.db.sqlalchemy_usuario_repository import SqlAlchemyUsuarioRepository
from app.infrastructure.ia.csv_registro import CsvRegistroLlamadas
from app.infrastructure.ia.gemini_client import GeminiClient
from app.infrastructure.ia.palabras import cargar_palabras
from app.infrastructure.seguridad.adaptadores import (
    BcryptHasher,
    CorreoConsola,
    CorreoSmtp,
    JwtTokens,
)


def get_docente_repository(db: Session = Depends(get_db)):
    return SqlAlchemyDocenteRepository(db)


def get_catalogo_repository(db: Session = Depends(get_db)):
    return SqlAlchemyCatalogoRepository(db)


def get_evaluacion_repository(db: Session = Depends(get_db)):
    return SqlAlchemyEvaluacionRepository(db)


def get_reporte_repository(db: Session = Depends(get_db)):
    return SqlAlchemyReporteRepository(db)


def get_usuario_repository(db: Session = Depends(get_db)):
    return SqlAlchemyUsuarioRepository(db)


def get_enviador_correo():
    if config.SMTP_SERVIDOR:
        return CorreoSmtp(config.SMTP_SERVIDOR, config.SMTP_PUERTO, config.SMTP_USUARIO,
                          config.SMTP_CLAVE, config.SMTP_REMITENTE, config.OTP_MINUTOS)
    return CorreoConsola()


def get_tokens():
    return JwtTokens(config.JWT_SECRETO, config.JWT_DIAS)


def get_cuenta_service(repo=Depends(get_usuario_repository), correo=Depends(get_enviador_correo),
                       tokens=Depends(get_tokens)):
    return CuentaService(repo, BcryptHasher(), tokens, correo, config.DOMINIOS_CORREO,
                         config.OTP_MINUTOS, excepciones=[config.ADMIN_CORREO])


bearer = HTTPBearer(auto_error=False)


def leer_token(request: Request, credenciales: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credenciales:
        return credenciales.credentials
    return request.cookies.get("token")


def get_sesion(token=Depends(leer_token), tokens=Depends(get_tokens)):
    return CuentaService.leer_sesion(tokens, token)


def get_sesion_opcional(token=Depends(leer_token), tokens=Depends(get_tokens)):
    if not token:
        return None
    try:
        return CuentaService.leer_sesion(tokens, token)
    except Exception:
        return None


def get_sesion_admin(sesion=Depends(get_sesion)):
    if not sesion.es_admin:
        raise SinPermiso("Esta acción es solo para administradores")
    return sesion


def get_catalogo_service(repo=Depends(get_catalogo_repository)):
    return CatalogoService(repo)


@lru_cache
def get_moderador():
    palabras = ModeradorPalabras(cargar_palabras(config.RUTA_PALABRAS))
    ia = None
    if config.MODERACION_IA and config.GEMINI_API_KEY:
        modelo = GeminiClient(config.GEMINI_API_KEY, config.MODELO_MODERACION,
                              config.MODERACION_TIMEOUT_MS, respuesta_json=True,
                              sin_razonamiento=True)
        ia = ModeradorIA(modelo, CsvRegistroLlamadas(config.RUTA_LOG_IA))
    return ModeracionService(palabras, ia)


def get_evaluacion_service(evaluaciones=Depends(get_evaluacion_repository),
                           docentes=Depends(get_docente_repository),
                           catalogo=Depends(get_catalogo_repository),
                           reportes=Depends(get_reporte_repository),
                           moderador=Depends(get_moderador)):
    return EvaluacionService(evaluaciones, docentes, catalogo, reportes, moderador)


def get_reporte_service(reportes=Depends(get_reporte_repository),
                        evaluaciones=Depends(get_evaluacion_repository)):
    return ReporteService(reportes, evaluaciones)


def get_docente_service(repo=Depends(get_docente_repository)):
    return DocenteService(repo)
