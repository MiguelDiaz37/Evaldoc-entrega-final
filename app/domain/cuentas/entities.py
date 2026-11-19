import re
from dataclasses import dataclass
from datetime import date, datetime

from app.domain.exceptions import CorreoNoInstitucional

ROLES = ("estudiante", "admin")
FORMATO_CORREO = re.compile(r"^[a-z0-9._%+-]+@([a-z0-9-]+\.)+[a-z]{2,}$")
MAX_INTENTOS_OTP = 5
ESPERA_ENTRE_CODIGOS_S = 60
MAX_CODIGOS_POR_HORA = 5


def normalizar_correo(correo, dominios, excepciones=()):
    correo = (correo or "").strip().lower()
    if not FORMATO_CORREO.match(correo):
        raise CorreoNoInstitucional("El correo no tiene un formato válido")
    if correo in excepciones:
        return correo
    if correo.split("@")[1] not in dominios:
        lista = ", ".join("@" + d for d in dominios)
        raise CorreoNoInstitucional(f"Solo se aceptan correos de estudiante ({lista})")
    return correo


@dataclass
class Usuario:
    correo_institucional: str
    rol: str = "estudiante"
    id_usuario: int | None = None
    fecha_registro: date | None = None

    @property
    def es_admin(self):
        return self.rol == "admin"


@dataclass
class CodigoOtp:

    id_usuario: int
    codigo_hash: str
    expira: datetime
    intentos: int = 0
    usado: bool = False
    id_codigo: int | None = None
    creado: datetime | None = None

    def vigente(self, ahora):
        return not self.usado and ahora < self.expira and self.intentos < MAX_INTENTOS_OTP


@dataclass
class Sesion:

    id_usuario: int
    rol: str

    @property
    def es_admin(self):
        return self.rol == "admin"
