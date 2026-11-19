from abc import ABC, abstractmethod

from app.domain.evaluacion_docente.entities import (
    Docente,
    Evaluacion,
    Facultad,
    Materia,
    Reporte,
    ResultadoModeracion,
)


class DocenteRepository(ABC):
    @abstractmethod
    def listar(self, id_facultad: int | None = None,
               id_materia: int | None = None) -> list[Docente]: ...

    @abstractmethod
    def obtener(self, id_docente: int) -> Docente | None: ...

    @abstractmethod
    def guardar(self, docente: Docente) -> Docente: ...

    @abstractmethod
    def eliminar(self, id_docente: int) -> None: ...


class CatalogoRepository(ABC):

    @abstractmethod
    def listar_facultades(self) -> list[Facultad]: ...

    @abstractmethod
    def listar_materias(self, id_facultad: int | None = None) -> list[Materia]: ...

    @abstractmethod
    def obtener_materia(self, id_materia: int) -> Materia | None: ...


class EvaluacionRepository(ABC):
    @abstractmethod
    def obtener(self, id_evaluacion: int) -> Evaluacion | None: ...

    @abstractmethod
    def existe(self, id_usuario: int, id_docente: int, id_materia: int) -> bool: ...

    @abstractmethod
    def listar_por_usuario(self, id_usuario: int) -> list[Evaluacion]: ...

    @abstractmethod
    def guardar(self, evaluacion: Evaluacion) -> Evaluacion: ...

    @abstractmethod
    def eliminar(self, id_evaluacion: int) -> None: ...

    @abstractmethod
    def marco_util(self, id_usuario: int, id_evaluacion: int) -> bool: ...

    @abstractmethod
    def marcar_util(self, id_usuario: int, id_evaluacion: int) -> None: ...

    @abstractmethod
    def quitar_util(self, id_usuario: int, id_evaluacion: int) -> None: ...

    @abstractmethod
    def ids_utiles(self, id_usuario: int) -> set[int]: ...


class ReporteRepository(ABC):
    @abstractmethod
    def obtener(self, id_reporte: int) -> Reporte | None: ...

    @abstractmethod
    def existe(self, id_usuario: int, id_evaluacion: int) -> bool: ...

    @abstractmethod
    def listar(self, estado: str | None = None) -> list[Reporte]: ...

    @abstractmethod
    def pendientes_de(self, id_evaluacion: int) -> list[Reporte]: ...

    @abstractmethod
    def guardar(self, reporte: Reporte) -> Reporte: ...


class Moderador(ABC):

    @abstractmethod
    def revisar(self, texto: str) -> ResultadoModeracion: ...
