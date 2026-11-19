from fastapi import APIRouter, Depends, Query, Response

from app.api.schemas import DocenteIn, DocenteOut, DocentePerfilOut
from app.application.docente_service import DocenteService
from app.domain.evaluacion_docente.entities import ordenar_evaluaciones, paginar
from app.container import get_docente_service, get_sesion_admin

router = APIRouter(prefix="/api/v1/docentes", tags=["Docentes"])


@router.get(
    "",
    response_model=list[DocenteOut],
    summary="Buscar y filtrar docentes",
    description="Público. Filtra por nombre, facultad o materia y ordena por `nombre`, "
    "`mejor` (promedio descendente) o `peor` (promedio ascendente). Con `pagina` y `tamano` "
    "devuelve solo esa página; el total viene en los encabezados `X-Total` y `X-Total-Paginas`.",
)
def listar_docentes(response: Response, nombre: str | None = None,
                    id_facultad: int | None = None, id_materia: int | None = None,
                    orden: str = Query("nombre", pattern="^(nombre|mejor|peor)$"),
                    pagina: int | None = Query(None, ge=1),
                    tamano: int = Query(20, ge=1, le=100),
                    service: DocenteService = Depends(get_docente_service)):
    docentes = service.listar(nombre, id_facultad, id_materia, orden)
    if pagina is None:
        return docentes
    resultado = paginar(docentes, pagina, tamano)
    response.headers["X-Total"] = str(resultado.total)
    response.headers["X-Total-Paginas"] = str(resultado.total_paginas)
    return resultado.items


@router.get(
    "/{id_docente}",
    response_model=DocentePerfilOut,
    summary="Perfil de un docente",
    description="Público. Devuelve el docente con su calificación promedio, sus materias "
    "y las evaluaciones publicadas (sin datos de quién evaluó), ordenadas por `utiles` "
    "(las más útiles primero) o `recientes`.",
    responses={404: {"description": "Docente no encontrado"}},
)
def obtener_docente(id_docente: int,
                    orden: str = Query("utiles", pattern="^(utiles|recientes)$"),
                    service: DocenteService = Depends(get_docente_service)):
    docente = service.obtener(id_docente)
    docente.evaluaciones = ordenar_evaluaciones(docente.evaluaciones, orden)
    return docente


@router.post(
    "",
    response_model=DocenteOut,
    status_code=201,
    summary="Crear docente (admin)",
    description="Solo administradores. La carga normal se hace con el script de datos iniciales.",
    dependencies=[Depends(get_sesion_admin)],
)
def crear_docente(datos: DocenteIn, service: DocenteService = Depends(get_docente_service)):
    return service.crear(datos.nombre, datos.foto_perfil)


@router.put(
    "/{id_docente}",
    response_model=DocenteOut,
    summary="Actualizar docente (admin)",
    responses={404: {"description": "Docente no encontrado"}},
    dependencies=[Depends(get_sesion_admin)],
)
def actualizar_docente(id_docente: int, datos: DocenteIn,
                       service: DocenteService = Depends(get_docente_service)):
    return service.actualizar(id_docente, datos.nombre, datos.foto_perfil)


@router.delete(
    "/{id_docente}",
    status_code=204,
    summary="Eliminar docente (admin)",
    description="Si el docente ya tiene evaluaciones devuelve 409 para no perderlas.",
    responses={404: {"description": "Docente no encontrado"},
               409: {"description": "Tiene evaluaciones"}},
    dependencies=[Depends(get_sesion_admin)],
)
def eliminar_docente(id_docente: int, service: DocenteService = Depends(get_docente_service)):
    service.eliminar(id_docente)
