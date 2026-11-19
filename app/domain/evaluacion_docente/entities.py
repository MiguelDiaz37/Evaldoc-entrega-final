import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

from app.domain.exceptions import DatoInvalido

MAX_COMENTARIO = 500
MIN_COMENTARIO = 10
MIN_RAZON = 10
MAX_RAZON = 300
ORDENES = ("nombre", "mejor", "peor")
ORDENES_EVALUACIONES = ("utiles", "recientes")

PUBLICADA = "publicada"
EN_REVISION = "en_revision"
OCULTA = "oculta"
ESTADOS_EVALUACION = (PUBLICADA, EN_REVISION, OCULTA)

ESTADOS_REPORTE = ("pendiente", "revisado", "descartado")
CATEGORIAS_REPORTE = {
    "ofensivo": "Lenguaje ofensivo o insultos",
    "datos_personales": "Datos personales del docente",
    "spam": "Spam o contenido sin relación",
    "falso": "Información falsa",
    "otro": "Otro",
}
ORIGEN_USUARIO = "usuario"
ORIGEN_IA = "ia"

PERMITIDO = "permitido"
DUDOSO = "dudoso"
BLOQUEADO = "bloqueado"
VEREDICTOS = (PERMITIDO, DUDOSO, BLOQUEADO)


@dataclass
class Facultad:
    nombre: str
    id_facultad: int | None = None


@dataclass
class Materia:
    nombre: str
    id_facultad: int
    id_materia: int | None = None
    nombre_facultad: str | None = None


def limpiar_comentario(comentario):
    if comentario is None:
        return None
    comentario = comentario.strip()
    return comentario or None


@dataclass
class ResultadoModeracion:
    veredicto: str
    motivo: str = ""
    categoria: str = ""

    def __post_init__(self):
        if self.veredicto not in VEREDICTOS:
            raise DatoInvalido("Veredicto de moderación inválido")
        if self.categoria not in CATEGORIAS_REPORTE:
            self.categoria = "ofensivo" if self.veredicto == BLOQUEADO else "otro"


@dataclass
class Evaluacion:

    puntaje: int | None = None
    comentario: str | None = None
    id_docente: int | None = None
    id_evaluacion: int | None = None
    id_usuario: int | None = None
    id_materia: int | None = None
    fecha: date | None = None
    nombre_materia: str | None = None
    estado: str = PUBLICADA
    fecha_edicion: datetime | None = None
    utiles: int = 0
    nombre_docente: str | None = None

    def __post_init__(self):
        self.comentario = limpiar_comentario(self.comentario)
        self.validar()

    def validar(self):
        if self.puntaje is None and self.comentario is None:
            raise DatoInvalido("La evaluación debe tener una calificación, un comentario o ambos")
        if self.puntaje is not None and not 1 <= self.puntaje <= 5:
            raise DatoInvalido("La calificación debe estar entre 1 y 5 estrellas")
        if self.comentario is not None:
            if len(self.comentario) < MIN_COMENTARIO:
                raise DatoInvalido(f"El comentario debe tener al menos {MIN_COMENTARIO} caracteres")
            if len(self.comentario) > MAX_COMENTARIO:
                raise DatoInvalido(f"El comentario no puede pasar de {MAX_COMENTARIO} caracteres")
        if self.estado not in ESTADOS_EVALUACION:
            raise DatoInvalido("Estado de evaluación inválido")

    @property
    def publicada(self):
        return self.estado == PUBLICADA

    @property
    def editada(self):
        return self.fecha_edicion is not None

    def es_de(self, id_usuario):
        return self.id_usuario == id_usuario

    def actualizar(self, puntaje, comentario, ahora):
        comentario = limpiar_comentario(comentario)
        if puntaje == self.puntaje and comentario == self.comentario:
            return False
        self.puntaje = puntaje
        self.comentario = comentario
        self.validar()
        self.fecha_edicion = ahora
        return True

    def aplicar_moderacion(self, resultado: ResultadoModeracion):
        self.estado = EN_REVISION if resultado.veredicto == BLOQUEADO else PUBLICADA


@dataclass
class Docente:
    nombre: str
    foto_perfil: str | None = None
    id_docente: int | None = None
    evaluaciones: list[Evaluacion] = field(default_factory=list)
    materias: list[Materia] = field(default_factory=list)

    def __post_init__(self):
        if not self.nombre or len(self.nombre.strip()) < 3:
            raise DatoInvalido("El nombre debe tener al menos 3 caracteres")
        self.nombre = self.nombre.strip()

    def puede_eliminarse(self):
        return len(self.evaluaciones) == 0

    @property
    def publicadas(self):
        return [e for e in self.evaluaciones if e.publicada]

    @property
    def calificaciones(self):
        return [e.puntaje for e in self.publicadas if e.puntaje is not None]

    @property
    def calificacion_promedio(self):
        if not self.calificaciones:
            return None
        return round(sum(self.calificaciones) / len(self.calificaciones), 1)

    @property
    def total_calificaciones(self):
        return len(self.calificaciones)

    @property
    def distribucion(self):
        return {k: self.calificaciones.count(k) for k in (5, 4, 3, 2, 1)}

    def dicta(self, id_materia):
        return any(m.id_materia == id_materia for m in self.materias)


def normalizar_texto(texto):
    sin_tildes = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn").lower().strip()


def filtrar_por_nombre(docentes, nombre):
    buscado = normalizar_texto(nombre)
    if not buscado:
        return docentes
    return [d for d in docentes if buscado in normalizar_texto(d.nombre)]


def ordenar_docentes(docentes, orden="nombre"):
    if orden not in ORDENES:
        raise DatoInvalido("El orden debe ser nombre, mejor o peor")
    if orden == "nombre":
        return sorted(docentes, key=lambda d: normalizar_texto(d.nombre))
    con_nota = [d for d in docentes if d.calificacion_promedio is not None]
    sin_nota = sorted([d for d in docentes if d.calificacion_promedio is None],
                      key=lambda d: normalizar_texto(d.nombre))
    con_nota.sort(key=lambda d: d.calificacion_promedio, reverse=(orden == "mejor"))
    return con_nota + sin_nota


def ordenar_evaluaciones(evaluaciones, orden="utiles"):
    if orden not in ORDENES_EVALUACIONES:
        raise DatoInvalido("El orden debe ser utiles o recientes")
    por_fecha = lambda e: (e.fecha or date.min, e.id_evaluacion or 0)
    if orden == "recientes":
        return sorted(evaluaciones, key=por_fecha, reverse=True)
    return sorted(evaluaciones, key=lambda e: (e.utiles, *por_fecha(e)), reverse=True)


@dataclass
class Pagina:
    items: list
    pagina: int
    total_paginas: int
    total: int

    @property
    def anterior(self):
        return self.pagina - 1 if self.pagina > 1 else None

    @property
    def siguiente(self):
        return self.pagina + 1 if self.pagina < self.total_paginas else None


def paginar(elementos, pagina=1, tamano=10):
    if tamano < 1:
        raise DatoInvalido("El tamaño de página debe ser mayor que cero")
    total = len(elementos)
    total_paginas = max(1, -(-total // tamano))
    pagina = min(max(1, pagina or 1), total_paginas)
    inicio = (pagina - 1) * tamano
    return Pagina(elementos[inicio:inicio + tamano], pagina, total_paginas, total)


@dataclass
class Reporte:

    id_evaluacion: int
    categoria: str
    motivo: str
    id_usuario: int | None = None
    origen: str = ORIGEN_USUARIO
    estado: str = "pendiente"
    id_reporte: int | None = None
    fecha: date | None = None
    evaluacion: Evaluacion | None = None
    nombre_docente: str | None = None
    resuelto_por: int | None = None
    correo_moderador: str | None = None
    fecha_resolucion: datetime | None = None

    def __post_init__(self):
        if self.categoria not in CATEGORIAS_REPORTE:
            raise DatoInvalido("Elige un tipo de problema válido")
        self.motivo = (self.motivo or "").strip()
        if not MIN_RAZON <= len(self.motivo) <= MAX_RAZON:
            raise DatoInvalido(f"Explica la razón del reporte (entre {MIN_RAZON} y {MAX_RAZON} caracteres)")
        self.validar_estado(self.estado)

    @property
    def nombre_categoria(self):
        return CATEGORIAS_REPORTE[self.categoria]

    @property
    def por_ia(self):
        return self.origen == ORIGEN_IA

    @staticmethod
    def validar_estado(estado):
        if estado not in ESTADOS_REPORTE:
            raise DatoInvalido("El estado debe ser pendiente, revisado o descartado")

    def cambiar_estado(self, estado):
        self.validar_estado(estado)
        self.estado = estado

    def cerrar(self, estado, ahora, id_moderador=None):
        if estado == "pendiente":
            raise DatoInvalido("Un reporte se cierra como revisado o descartado")
        self.cambiar_estado(estado)
        self.resuelto_por = id_moderador
        self.fecha_resolucion = ahora
