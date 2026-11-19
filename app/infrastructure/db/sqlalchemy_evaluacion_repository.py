from sqlalchemy.orm import Session

from app.domain.evaluacion_docente.entities import Reporte
from app.domain.evaluacion_docente.ports import EvaluacionRepository, ReporteRepository
from app.infrastructure.db.models import EvaluacionORM, ReporteORM, VotoUtilORM
from app.infrastructure.db.sqlalchemy_docente_repository import evaluacion_a_entidad


class SqlAlchemyEvaluacionRepository(EvaluacionRepository):
    def __init__(self, db: Session):
        self.db = db

    def obtener(self, id_evaluacion):
        fila = self.db.get(EvaluacionORM, id_evaluacion)
        return evaluacion_a_entidad(fila) if fila else None

    def existe(self, id_usuario, id_docente, id_materia):
        return self.db.query(EvaluacionORM).filter_by(
            id_usuario=id_usuario, id_docente=id_docente, id_materia=id_materia
        ).first() is not None

    def listar_por_usuario(self, id_usuario):
        filas = (self.db.query(EvaluacionORM).filter_by(id_usuario=id_usuario)
                 .order_by(EvaluacionORM.fecha.desc(), EvaluacionORM.id_evaluacion.desc()).all())
        return [evaluacion_a_entidad(f) for f in filas]

    def guardar(self, evaluacion):
        if evaluacion.id_evaluacion is None:
            fila = EvaluacionORM(id_usuario=evaluacion.id_usuario,
                                 id_docente=evaluacion.id_docente,
                                 id_materia=evaluacion.id_materia)
            self.db.add(fila)
        else:
            fila = self.db.get(EvaluacionORM, evaluacion.id_evaluacion)
        fila.puntaje = evaluacion.puntaje
        fila.comentario = evaluacion.comentario
        fila.estado = evaluacion.estado
        fila.fecha_edicion = evaluacion.fecha_edicion
        self.db.commit()
        self.db.refresh(fila)
        return evaluacion_a_entidad(fila)

    def eliminar(self, id_evaluacion):
        fila = self.db.get(EvaluacionORM, id_evaluacion)
        if fila:
            self.db.delete(fila)
            self.db.commit()

    def marco_util(self, id_usuario, id_evaluacion):
        return self.db.get(VotoUtilORM, (id_usuario, id_evaluacion)) is not None

    def marcar_util(self, id_usuario, id_evaluacion):
        self.db.add(VotoUtilORM(id_usuario=id_usuario, id_evaluacion=id_evaluacion))
        self.db.commit()

    def quitar_util(self, id_usuario, id_evaluacion):
        fila = self.db.get(VotoUtilORM, (id_usuario, id_evaluacion))
        if fila:
            self.db.delete(fila)
            self.db.commit()

    def ids_utiles(self, id_usuario):
        filas = self.db.query(VotoUtilORM.id_evaluacion).filter_by(id_usuario=id_usuario).all()
        return {f[0] for f in filas}


def reporte_a_entidad(fila: ReporteORM) -> Reporte:
    return Reporte(id_reporte=fila.id_reporte, id_evaluacion=fila.id_evaluacion,
                   id_usuario=fila.id_usuario, categoria=fila.categoria, origen=fila.origen,
                   motivo=fila.motivo, estado=fila.estado, fecha=fila.fecha,
                   evaluacion=evaluacion_a_entidad(fila.evaluacion),
                   nombre_docente=fila.evaluacion.docente.nombre,
                   resuelto_por=fila.resuelto_por, fecha_resolucion=fila.fecha_resolucion,
                   correo_moderador=fila.moderador.correo_institucional if fila.moderador else None)


class SqlAlchemyReporteRepository(ReporteRepository):
    def __init__(self, db: Session):
        self.db = db

    def obtener(self, id_reporte):
        fila = self.db.get(ReporteORM, id_reporte)
        return reporte_a_entidad(fila) if fila else None

    def existe(self, id_usuario, id_evaluacion):
        return self.db.query(ReporteORM).filter_by(
            id_usuario=id_usuario, id_evaluacion=id_evaluacion
        ).first() is not None

    def listar(self, estado=None):
        query = self.db.query(ReporteORM)
        if estado:
            query = query.filter_by(estado=estado)
        filas = query.order_by(ReporteORM.fecha_resolucion.desc().nullsfirst(), ReporteORM.fecha.desc(),
                               ReporteORM.id_reporte.desc()).all()
        return [reporte_a_entidad(f) for f in filas]

    def pendientes_de(self, id_evaluacion):
        filas = self.db.query(ReporteORM).filter_by(id_evaluacion=id_evaluacion,
                                                    estado="pendiente").all()
        return [reporte_a_entidad(f) for f in filas]

    def guardar(self, reporte):
        if reporte.id_reporte is None:
            fila = ReporteORM(id_evaluacion=reporte.id_evaluacion, id_usuario=reporte.id_usuario,
                              categoria=reporte.categoria, origen=reporte.origen,
                              motivo=reporte.motivo)
            self.db.add(fila)
        else:
            fila = self.db.get(ReporteORM, reporte.id_reporte)
        fila.estado = reporte.estado
        fila.resuelto_por = reporte.resuelto_por
        fila.fecha_resolucion = reporte.fecha_resolucion
        self.db.commit()
        self.db.refresh(fila)
        return reporte_a_entidad(fila)
