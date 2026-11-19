from app.domain.evaluacion_docente.entities import Docente, filtrar_por_nombre, ordenar_docentes
from app.domain.evaluacion_docente.ports import CatalogoRepository, DocenteRepository
from app.domain.exceptions import DocenteConEvaluaciones, DocenteNoEncontrado


class DocenteService:
    def __init__(self, repo: DocenteRepository):
        self.repo = repo

    def listar(self, nombre=None, id_facultad=None, id_materia=None, orden="nombre"):
        docentes = self.repo.listar(id_facultad, id_materia)
        return ordenar_docentes(filtrar_por_nombre(docentes, nombre), orden)

    def obtener(self, id_docente):
        docente = self.repo.obtener(id_docente)
        if docente is None:
            raise DocenteNoEncontrado("Docente no encontrado")
        return docente

    def crear(self, nombre, foto_perfil=None):
        return self.repo.guardar(Docente(nombre=nombre, foto_perfil=foto_perfil))

    def actualizar(self, id_docente, nombre, foto_perfil=None):
        docente = self.obtener(id_docente)
        docente.nombre = Docente(nombre=nombre).nombre
        docente.foto_perfil = foto_perfil
        return self.repo.guardar(docente)

    def eliminar(self, id_docente):
        docente = self.obtener(id_docente)
        if not docente.puede_eliminarse():
            raise DocenteConEvaluaciones("El docente tiene evaluaciones y no se puede eliminar")
        self.repo.eliminar(id_docente)


class CatalogoService:
    def __init__(self, repo: CatalogoRepository):
        self.repo = repo

    def facultades(self):
        return self.repo.listar_facultades()

    def materias(self, id_facultad=None):
        return self.repo.listar_materias(id_facultad)
