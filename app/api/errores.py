import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

from app.domain import exceptions as ex

log = logging.getLogger("evaldoc.errores")

CODIGOS = {
    ex.DatoInvalido: 422,
    ex.CorreoNoInstitucional: 422,
    ex.NoAutenticado: 401,
    ex.CodigoInvalido: 401,
    ex.SinPermiso: 403,
    ex.DocenteNoEncontrado: 404,
    ex.MateriaNoEncontrada: 404,
    ex.EvaluacionNoEncontrada: 404,
    ex.ReporteNoEncontrado: 404,
    ex.DocenteConEvaluaciones: 409,
    ex.EvaluacionDuplicada: 409,
    ex.ReporteDuplicado: 409,
    ex.DemasiadosIntentos: 429,
    ex.CorreoNoEnviado: 503,
    ex.IALimiteAlcanzado: 429,
    ex.IAError: 502,
    ex.IANoConfigurada: 503,
    ex.IATiempoAgotado: 504,
}


def codigo_de(error):
    return CODIGOS.get(type(error), 400)


def registrar_manejadores(app: FastAPI):
    async def manejar_dominio(request: Request, error: ex.ErrorDominio):
        return JSONResponse(status_code=codigo_de(error), content={"detail": str(error)})

    async def manejar_integridad(request: Request, error: IntegrityError):
        log.warning("Violacion de integridad: %s", error.orig)
        return JSONResponse(status_code=409,
                            content={"detail": "El registro ya existe o viola una regla de datos"})

    async def manejar_conexion(request: Request, error: OperationalError):
        log.error("Error de base de datos: %s", error.orig)
        return JSONResponse(status_code=503,
                            content={"detail": "No hay conexión con la base de datos. Intenta más tarde"})

    app.add_exception_handler(ex.ErrorDominio, manejar_dominio)
    app.add_exception_handler(IntegrityError, manejar_integridad)
    app.add_exception_handler(OperationalError, manejar_conexion)
