from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.cuentas.entities import CodigoOtp, Sesion, Usuario


class UsuarioRepository(ABC):
    @abstractmethod
    def por_correo(self, correo: str) -> Usuario | None: ...

    @abstractmethod
    def guardar(self, usuario: Usuario) -> Usuario: ...

    @abstractmethod
    def ultimo_codigo(self, id_usuario: int) -> CodigoOtp | None: ...

    @abstractmethod
    def guardar_codigo(self, codigo: CodigoOtp) -> CodigoOtp: ...

    @abstractmethod
    def contar_codigos_desde(self, id_usuario: int, desde: datetime) -> int: ...

    @abstractmethod
    def eliminar_codigo(self, id_codigo: int) -> None: ...


class Hasher(ABC):
    @abstractmethod
    def hashear(self, texto: str) -> str: ...

    @abstractmethod
    def verificar(self, texto: str, hash_guardado: str) -> bool: ...


class GestorTokens(ABC):
    @abstractmethod
    def crear(self, sesion: Sesion) -> str: ...

    @abstractmethod
    def leer(self, token: str) -> Sesion: ...


class EnviadorCorreo(ABC):
    @abstractmethod
    def enviar_codigo(self, correo: str, codigo: str) -> None: ...
