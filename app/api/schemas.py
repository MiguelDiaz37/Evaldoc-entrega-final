from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

class SolicitarCodigoIn(BaseModel):
    correo_institucional: str = Field(examples=["estudiante@umb.edu.co"])


class SolicitarCodigoOut(BaseModel):
    mensaje: str
    codigo_demo: str | None = Field(
        default=None, description="Solo aparece con MODO_DEMO=true, para la sustentación"
    )


class VerificarCodigoIn(BaseModel):
    correo_institucional: str = Field(examples=["estudiante@umb.edu.co"])
    codigo: str = Field(min_length=6, max_length=6, examples=["123456"])


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: str


class SesionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    rol: str


class FacultadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_facultad: int
    nombre: str


class MateriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_materia: int
    nombre: str
    id_facultad: int
    nombre_facultad: str | None = None


class DocenteIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=150, examples=["Carlos Perez"])
    foto_perfil: str | None = None


class DocenteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_docente: int
    nombre: str
    foto_perfil: str | None = None
    calificacion_promedio: float | None = None
    total_calificaciones: int = 0
    materias: list[MateriaOut] = []


class EvaluacionPublicaOut(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id_evaluacion: int
    puntaje: int | None = None
    comentario: str | None = None
    nombre_materia: str | None = None
    fecha: date | None = None
    fecha_edicion: datetime | None = Field(default=None, description="Si no es nulo, fue editada")
    utiles: int = 0


class DocentePerfilOut(DocenteOut):
    evaluaciones: list[EvaluacionPublicaOut] = Field(default=[], validation_alias="publicadas")


class EvaluacionIn(BaseModel):
    id_docente: int = Field(examples=[1])
    id_materia: int = Field(examples=[1])
    puntaje: int | None = Field(default=None, examples=[4])
    comentario: str | None = Field(default=None, examples=["Explica muy bien y resuelve dudas"])


class EvaluacionEditarIn(BaseModel):
    puntaje: int | None = Field(default=None, examples=[5])
    comentario: str | None = Field(default=None, examples=["Mejoró mucho en el segundo corte"])


class EvaluacionOut(EvaluacionPublicaOut):
    id_docente: int
    id_materia: int
    estado: str = Field(description="publicada, en_revision u oculta")


class UtilOut(BaseModel):
    util: bool = Field(description="True si quedó marcada como útil por ti")
    utiles: int


class ReporteIn(BaseModel):
    id_evaluacion: int = Field(examples=[1])
    categoria: str = Field(examples=["ofensivo"],
                           description="ofensivo, datos_personales, spam, falso u otro")
    motivo: str = Field(examples=["Insulta al profesor en vez de hablar de la clase"],
                        description="Razón escrita, entre 10 y 300 caracteres")


class ResolverReporteIn(BaseModel):
    accion: str = Field(examples=["ocultar"], description="publicar u ocultar la evaluación")


class ReporteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_reporte: int
    id_evaluacion: int
    categoria: str
    nombre_categoria: str
    origen: str = Field(description="usuario o ia")
    motivo: str
    estado: str
    fecha: date | None = None
    nombre_docente: str | None = None
    evaluacion: EvaluacionPublicaOut | None = None
    resuelto_por: int | None = Field(default=None, description="id del moderador que lo cerró")
    fecha_resolucion: datetime | None = None
