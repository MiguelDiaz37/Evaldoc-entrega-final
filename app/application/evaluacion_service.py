from datetime import datetime

from app.domain.cuentas.entities import Sesion
from app.domain.evaluacion_docente.entities import (
    BLOQUEADO,
    OCULTA,
    ORIGEN_IA,
    PERMITIDO,
    PUBLICADA,
    Evaluacion,
    Reporte,
    ResultadoModeracion,
)
from app.domain.evaluacion_docente.ports import (
    CatalogoRepository,
    DocenteRepository,
    EvaluacionRepository,
    Moderador,
    ReporteRepository,
)
from app.domain.exceptions import (
    DatoInvalido,
    DocenteNoEncontrado,
    EvaluacionDuplicada,
    EvaluacionNoEncontrada,
    MateriaNoEncontrada,
    ReporteDuplicado,
    ReporteNoEncontrado,
    SinPermiso,
)

ACCIONES_MODERADOR = ("publicar", "ocultar")


class EvaluacionService:
    def __init__(self, evaluaciones: EvaluacionRepository, docentes: DocenteRepository,
                 catalogo: CatalogoRepository, reportes: ReporteRepository,
                 moderador: Moderador, reloj=datetime.now):
        self.evaluaciones = evaluaciones
        self.docentes = docentes
        self.catalogo = catalogo
        self.reportes = reportes
        self.moderador = moderador
        self.reloj = reloj

    def obtener(self, id_evaluacion):
        evaluacion = self.evaluaciones.obtener(id_evaluacion)
        if evaluacion is None:
            raise EvaluacionNoEncontrada("Evaluación no encontrada")
        return evaluacion

    def crear(self, sesion: Sesion, id_docente, id_materia, puntaje=None, comentario=None):
        docente = self.docentes.obtener(id_docente)
        if docente is None:
            raise DocenteNoEncontrado("Docente no encontrado")
        if self.catalogo.obtener_materia(id_materia) is None:
            raise MateriaNoEncontrada("Materia no encontrada")
        if not docente.dicta(id_materia):
            raise DatoInvalido("El docente no dicta esa materia")
        if self.evaluaciones.existe(sesion.id_usuario, id_docente, id_materia):
            raise EvaluacionDuplicada("Ya evaluaste a este docente en esa materia. Puedes editar tu evaluación")

        evaluacion = Evaluacion(puntaje=puntaje, comentario=comentario, id_docente=id_docente,
                                id_usuario=sesion.id_usuario, id_materia=id_materia)
        resultado = self.moderador.revisar(evaluacion.comentario)
        evaluacion.aplicar_moderacion(resultado)
        guardada = self.evaluaciones.guardar(evaluacion)
        self._reportar_si_hace_falta(guardada, resultado)
        return guardada

    def editar(self, sesion: Sesion, id_evaluacion, puntaje=None, comentario=None):
        evaluacion = self.obtener(id_evaluacion)
        if not evaluacion.es_de(sesion.id_usuario):
            raise SinPermiso("Solo puedes editar tus propias evaluaciones")
        if evaluacion.estado == OCULTA:
            raise SinPermiso("Un moderador ocultó esta evaluación y ya no se puede editar")

        if not evaluacion.actualizar(puntaje, comentario, self.reloj()):
            return evaluacion

        resultado = self.moderador.revisar(evaluacion.comentario)
        evaluacion.aplicar_moderacion(resultado)
        guardada = self.evaluaciones.guardar(evaluacion)
        if resultado.veredicto == PERMITIDO:
            for reporte in self.reportes.pendientes_de(id_evaluacion):
                if reporte.por_ia:
                    reporte.cerrar("descartado", self.reloj())
                    self.reportes.guardar(reporte)
        else:
            self._reportar_si_hace_falta(guardada, resultado)
        return guardada

    def eliminar(self, sesion: Sesion, id_evaluacion):
        evaluacion = self.obtener(id_evaluacion)
        if not evaluacion.es_de(sesion.id_usuario) and not sesion.es_admin:
            raise SinPermiso("Solo puedes eliminar tus propias evaluaciones")
        self.evaluaciones.eliminar(id_evaluacion)

    def mias(self, sesion: Sesion):
        return self.evaluaciones.listar_por_usuario(sesion.id_usuario)

    def alternar_util(self, sesion: Sesion, id_evaluacion):
        evaluacion = self.obtener(id_evaluacion)
        if not evaluacion.publicada:
            raise EvaluacionNoEncontrada("Evaluación no encontrada")
        if evaluacion.es_de(sesion.id_usuario):
            raise DatoInvalido("No puedes marcar como útil tu propia evaluación")

        if self.evaluaciones.marco_util(sesion.id_usuario, id_evaluacion):
            self.evaluaciones.quitar_util(sesion.id_usuario, id_evaluacion)
            marcada = False
        else:
            self.evaluaciones.marcar_util(sesion.id_usuario, id_evaluacion)
            marcada = True
        return marcada, self.obtener(id_evaluacion).utiles

    def ids_utiles(self, sesion: Sesion | None):
        return self.evaluaciones.ids_utiles(sesion.id_usuario) if sesion else set()

    def _reportar_si_hace_falta(self, evaluacion, resultado: ResultadoModeracion):
        if resultado.veredicto == PERMITIDO:
            return
        ya_hay = any(r.por_ia for r in self.reportes.pendientes_de(evaluacion.id_evaluacion))
        if ya_hay:
            return
        prefijo = "Oculta hasta revisión" if resultado.veredicto == BLOQUEADO else "Publicada, revisar"
        motivo = f"{prefijo}: {resultado.motivo or 'marcado por la moderación automática'}"
        self.reportes.guardar(Reporte(
            id_evaluacion=evaluacion.id_evaluacion,
            categoria=resultado.categoria,
            motivo=motivo[:300], origen=ORIGEN_IA,
        ))


class ReporteService:
    def __init__(self, reportes: ReporteRepository, evaluaciones: EvaluacionRepository,
                 reloj=datetime.now):
        self.reportes = reportes
        self.evaluaciones = evaluaciones
        self.reloj = reloj

    def reportar(self, sesion: Sesion, id_evaluacion, categoria, motivo):
        evaluacion = self.evaluaciones.obtener(id_evaluacion)
        if evaluacion is None or not evaluacion.publicada:
            raise EvaluacionNoEncontrada("Evaluación no encontrada")
        if evaluacion.es_de(sesion.id_usuario):
            raise DatoInvalido("No puedes reportar tu propia evaluación")
        if self.reportes.existe(sesion.id_usuario, id_evaluacion):
            raise ReporteDuplicado("Ya reportaste esta evaluación")
        reporte = Reporte(id_evaluacion=id_evaluacion, id_usuario=sesion.id_usuario,
                          categoria=categoria, motivo=motivo)
        return self.reportes.guardar(reporte)

    def listar(self, sesion: Sesion, estado=None):
        self._solo_admin(sesion)
        if estado:
            Reporte.validar_estado(estado)
        return self.reportes.listar(estado)

    def resolver(self, sesion: Sesion, id_reporte, accion):
        self._solo_admin(sesion)
        if accion not in ACCIONES_MODERADOR:
            raise DatoInvalido("La acción debe ser publicar u ocultar")
        reporte = self.reportes.obtener(id_reporte)
        if reporte is None:
            raise ReporteNoEncontrado("Reporte no encontrado")
        if reporte.estado != "pendiente":
            raise DatoInvalido("Este reporte ya fue resuelto")

        evaluacion = self.evaluaciones.obtener(reporte.id_evaluacion)
        evaluacion.estado = PUBLICADA if accion == "publicar" else OCULTA
        self.evaluaciones.guardar(evaluacion)

        nuevo_estado = "descartado" if accion == "publicar" else "revisado"
        ahora = self.reloj()
        for pendiente in self.reportes.pendientes_de(reporte.id_evaluacion):
            pendiente.cerrar(nuevo_estado, ahora, sesion.id_usuario)
            self.reportes.guardar(pendiente)
        return self.reportes.obtener(id_reporte)

    def contar_pendientes(self, sesion: Sesion):
        return len(self.listar(sesion, "pendiente"))

    @staticmethod
    def _solo_admin(sesion):
        if sesion is None or not sesion.es_admin:
            raise SinPermiso("Solo un administrador puede gestionar reportes")

