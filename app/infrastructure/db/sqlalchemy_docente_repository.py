from datetime import date

from sqlalchemy.orm import Session, selectinload

from app.domain.evaluacion_docente.entities import Docente, Evaluacion, Facultad, Materia
from app.domain.evaluacion_docente.ports import CatalogoRepository, DocenteRepository
from app.infrastructure.db.models import DocenteORM, EvaluacionORM, FacultadORM, MateriaORM


def materia_a_entidad(fila: MateriaORM) -> Materia:
    return Materia(id_materia=fila.id_materia, nombre=fila.nombre, id_facultad=fila.id_facultad,
                   nombre_facultad=fila.facultad.nombre if fila.facultad else None)


def evaluacion_a_entidad(fila: EvaluacionORM) -> Evaluacion:
    return Evaluacion(id_evaluacion=fila.id_evaluacion, id_docente=fila.id_docente,
                      id_usuario=fila.id_usuario, id_materia=fila.id_materia,
                      puntaje=fila.puntaje, comentario=fila.comentario, fecha=fila.fecha,
                      estado=fila.estado or "publicada", fecha_edicion=fila.fecha_edicion,
                      utiles=len(fila.votos_utiles),
                      nombre_materia=fila.materia.nombre if fila.materia else None,
                      nombre_docente=fila.docente.nombre if fila.docente else None)


def a_entidad(fila: DocenteORM) -> Docente:
    evaluaciones = sorted((evaluacion_a_entidad(e) for e in fila.evaluaciones),
                          key=lambda e: (e.utiles, e.fecha or date.min, e.id_evaluacion),
                          reverse=True)
    materias = [materia_a_entidad(m) for m in sorted(fila.materias, key=lambda m: m.nombre)]
    return Docente(id_docente=fila.id_docente, nombre=fila.nombre, foto_perfil=fila.foto_perfil,
                   evaluaciones=evaluaciones, materias=materias)


class SqlAlchemyDocenteRepository(DocenteRepository):
    def __init__(self, db: Session):
        self.db = db

    def listar(self, id_facultad=None, id_materia=None):
        query = self.db.query(DocenteORM).options(
            selectinload(DocenteORM.evaluaciones).selectinload(EvaluacionORM.votos_utiles),
            selectinload(DocenteORM.materias)
        )
        if id_materia:
            query = query.filter(DocenteORM.materias.any(MateriaORM.id_materia == id_materia))
        if id_facultad:
            query = query.filter(DocenteORM.materias.any(MateriaORM.id_facultad == id_facultad))
        return [a_entidad(f) for f in query.all()]

    def obtener(self, id_docente):
        fila = self.db.get(DocenteORM, id_docente)
        return a_entidad(fila) if fila else None

    def guardar(self, docente):
        if docente.id_docente is None:
            fila = DocenteORM()
            self.db.add(fila)
        else:
            fila = self.db.get(DocenteORM, docente.id_docente)
        fila.nombre = docente.nombre
        fila.foto_perfil = docente.foto_perfil
        self.db.commit()
        self.db.refresh(fila)
        return a_entidad(fila)

    def eliminar(self, id_docente):
        fila = self.db.get(DocenteORM, id_docente)
        if fila:
            self.db.delete(fila)
            self.db.commit()


class SqlAlchemyCatalogoRepository(CatalogoRepository):
    def __init__(self, db: Session):
        self.db = db

    def listar_facultades(self):
        filas = self.db.query(FacultadORM).order_by(FacultadORM.nombre).all()
        return [Facultad(id_facultad=f.id_facultad, nombre=f.nombre) for f in filas]

    def listar_materias(self, id_facultad=None):
        query = self.db.query(MateriaORM)
        if id_facultad:
            query = query.filter(MateriaORM.id_facultad == id_facultad)
        return [materia_a_entidad(m) for m in query.order_by(MateriaORM.nombre).all()]

    def obtener_materia(self, id_materia):
        fila = self.db.get(MateriaORM, id_materia)
        return materia_a_entidad(fila) if fila else None
