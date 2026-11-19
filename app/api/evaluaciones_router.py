from fastapi import APIRouter, Depends

from app.api.schemas import (
    EvaluacionEditarIn,
    EvaluacionIn,
    EvaluacionOut,
    FacultadOut,
    MateriaOut,
    ReporteIn,
    ReporteOut,
    ResolverReporteIn,
    UtilOut,
)
from app.application.docente_service import CatalogoService
from app.application.evaluacion_service import EvaluacionService, ReporteService
from app.container import (
    get_catalogo_service,
    get_evaluacion_service,
    get_reporte_service,
    get_sesion,
)

catalogo = APIRouter(prefix="/api/v1", tags=["Catálogo"])
evaluaciones = APIRouter(prefix="/api/v1/evaluaciones", tags=["Evaluaciones"])
reportes = APIRouter(prefix="/api/v1/reportes", tags=["Moderación"])


@catalogo.get("/facultades", response_model=list[FacultadOut], summary="Listar facultades")
def listar_facultades(service: CatalogoService = Depends(get_catalogo_service)):
    return service.facultades()


@catalogo.get("/materias", response_model=list[MateriaOut], summary="Listar materias",
              description="Se puede filtrar por facultad con `id_facultad`.")
def listar_materias(id_facultad: int | None = None,
                    service: CatalogoService = Depends(get_catalogo_service)):
    return service.materias(id_facultad)


@evaluaciones.post(
    "",
    response_model=EvaluacionOut,
    status_code=201,
    summary="Calificar y/o comentar a un docente",
    description="Necesita token. Debe tener calificación (1 a 5), comentario (10 a 500 "
    "caracteres) o ambos. Solo se permite una evaluación por docente y materia. El comentario "
    "pasa por la moderación automática: si es ofensivo queda `en_revision` (oculto) hasta que "
    "un moderador decida; si es dudoso se publica y se crea un reporte automático.",
    responses={401: {"description": "Sin sesión"}, 404: {"description": "Docente o materia no existe"},
               409: {"description": "Ya evaluó a ese docente en esa materia"}},
)
def crear_evaluacion(datos: EvaluacionIn, sesion=Depends(get_sesion),
                     service: EvaluacionService = Depends(get_evaluacion_service)):
    return service.crear(sesion, datos.id_docente, datos.id_materia, datos.puntaje,
                         datos.comentario)


@evaluaciones.get("/mias", response_model=list[EvaluacionOut],
                  summary="Mis evaluaciones")
def mis_evaluaciones(sesion=Depends(get_sesion),
                     service: EvaluacionService = Depends(get_evaluacion_service)):
    return service.mias(sesion)


@evaluaciones.put(
    "/{id_evaluacion}",
    response_model=EvaluacionOut,
    summary="Editar una evaluación propia",
    description="Si cambia algo se guarda `fecha_edicion` y el comentario se vuelve a moderar.",
    responses={403: {"description": "No es su evaluación"}, 404: {"description": "No existe"}},
)
def editar_evaluacion(id_evaluacion: int, datos: EvaluacionEditarIn, sesion=Depends(get_sesion),
                      service: EvaluacionService = Depends(get_evaluacion_service)):
    return service.editar(sesion, id_evaluacion, datos.puntaje, datos.comentario)


@evaluaciones.delete(
    "/{id_evaluacion}",
    status_code=204,
    summary="Eliminar una evaluación",
    description="El dueño puede eliminar la suya; el administrador puede eliminar cualquiera.",
    responses={403: {"description": "Sin permiso"}, 404: {"description": "No existe"}},
)
def eliminar_evaluacion(id_evaluacion: int, sesion=Depends(get_sesion),
                        service: EvaluacionService = Depends(get_evaluacion_service)):
    service.eliminar(sesion, id_evaluacion)


@evaluaciones.post(
    "/{id_evaluacion}/util",
    response_model=UtilOut,
    summary="Marcar o quitar \"Útil\"",
    description="Si no la habías marcado la marca, y si ya la habías marcado la desmarca. "
    "Un usuario solo puede marcar una vez cada evaluación y no puede marcar las suyas.",
)
def alternar_util(id_evaluacion: int, sesion=Depends(get_sesion),
                  service: EvaluacionService = Depends(get_evaluacion_service)):
    util, total = service.alternar_util(sesion, id_evaluacion)
    return UtilOut(util=util, utiles=total)


@reportes.post(
    "",
    response_model=ReporteOut,
    status_code=201,
    summary="Reportar una evaluación",
    responses={409: {"description": "Ya la reportó"}},
)
def reportar(datos: ReporteIn, sesion=Depends(get_sesion),
             service: ReporteService = Depends(get_reporte_service)):
    return service.reportar(sesion, datos.id_evaluacion, datos.categoria, datos.motivo)


@reportes.get("", response_model=list[ReporteOut], summary="Listar reportes (admin)",
              description="Filtra por `estado`: pendiente, revisado o descartado.")
def listar_reportes(estado: str | None = None, sesion=Depends(get_sesion),
                    service: ReporteService = Depends(get_reporte_service)):
    return service.listar(sesion, estado)


@reportes.post("/{id_reporte}/resolver", response_model=ReporteOut,
               summary="Resolver un reporte (admin)",
               description="`publicar`: la evaluación se muestra y los reportes pendientes quedan "
               "descartados. `ocultar`: la evaluación deja de verse (no se borra) y los reportes "
               "quedan revisados.")
def resolver_reporte(id_reporte: int, datos: ResolverReporteIn, sesion=Depends(get_sesion),
                     service: ReporteService = Depends(get_reporte_service)):
    return service.resolver(sesion, id_reporte, datos.accion)
