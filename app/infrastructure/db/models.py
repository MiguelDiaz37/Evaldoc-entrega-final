from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.infrastructure.db.database import Base

docente_materia = Table(
    "docente_materia",
    Base.metadata,
    Column("id_docente", Integer, ForeignKey("docente.id_docente", ondelete="CASCADE"),
           primary_key=True),
    Column("id_materia", Integer, ForeignKey("materia.id_materia", ondelete="CASCADE"),
           primary_key=True),
)


class UsuarioORM(Base):
    __tablename__ = "usuario"
    __table_args__ = (CheckConstraint("rol IN ('estudiante', 'admin')", name="chk_usuario_rol"),)

    id_usuario = Column(Integer, primary_key=True)
    correo_institucional = Column(String(150), nullable=False, unique=True)
    rol = Column(String(20), nullable=False, default="estudiante")
    fecha_registro = Column(Date, nullable=False, default=date.today)


class CodigoOtpORM(Base):

    __tablename__ = "codigo_otp"

    id_codigo = Column(Integer, primary_key=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"),
                        nullable=False)
    codigo_hash = Column(String(100), nullable=False)
    expira = Column(DateTime, nullable=False)
    intentos = Column(Integer, nullable=False, default=0)
    usado = Column(Boolean, nullable=False, default=False)
    creado = Column(DateTime, nullable=False, default=datetime.now)


class FacultadORM(Base):
    __tablename__ = "facultad"

    id_facultad = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False, unique=True)

    materias = relationship("MateriaORM", back_populates="facultad")


class MateriaORM(Base):
    __tablename__ = "materia"

    id_materia = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    id_facultad = Column(Integer, ForeignKey("facultad.id_facultad"), nullable=False)

    facultad = relationship("FacultadORM", back_populates="materias")
    docentes = relationship("DocenteORM", secondary=docente_materia, back_populates="materias")


class DocenteORM(Base):
    __tablename__ = "docente"

    id_docente = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    foto_perfil = Column(String(300), nullable=True)

    evaluaciones = relationship("EvaluacionORM", back_populates="docente")
    materias = relationship("MateriaORM", secondary=docente_materia, back_populates="docentes")


class EvaluacionORM(Base):
    __tablename__ = "evaluacion"
    __table_args__ = (
        CheckConstraint("puntaje BETWEEN 1 AND 5", name="chk_evaluacion_puntaje"),
        CheckConstraint("puntaje IS NOT NULL OR comentario IS NOT NULL",
                        name="chk_evaluacion_no_vacia"),
        UniqueConstraint("id_usuario", "id_docente", "id_materia", name="uq_evaluacion_unica"),
        CheckConstraint("estado IN ('publicada', 'en_revision', 'oculta')",
                        name="chk_evaluacion_estado"),
    )

    id_evaluacion = Column(Integer, primary_key=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario"), nullable=False)
    id_docente = Column(Integer, ForeignKey("docente.id_docente"), nullable=False)
    id_materia = Column(Integer, ForeignKey("materia.id_materia"), nullable=False)
    puntaje = Column(SmallInteger)
    comentario = Column(String(500))
    fecha = Column(Date, nullable=False, default=date.today)
    estado = Column(String(20), nullable=False, default="publicada")
    fecha_edicion = Column(DateTime, nullable=True)

    docente = relationship("DocenteORM", back_populates="evaluaciones")
    materia = relationship("MateriaORM")
    reportes = relationship("ReporteORM", back_populates="evaluacion",
                            cascade="all, delete-orphan")
    votos_utiles = relationship("VotoUtilORM", cascade="all, delete-orphan")


class VotoUtilORM(Base):

    __tablename__ = "voto_util"

    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"),
                        primary_key=True)
    id_evaluacion = Column(Integer, ForeignKey("evaluacion.id_evaluacion", ondelete="CASCADE"),
                           primary_key=True)
    fecha = Column(DateTime, nullable=False, default=datetime.now)


class ReporteORM(Base):
    __tablename__ = "reporte"
    __table_args__ = (
        CheckConstraint("estado IN ('pendiente', 'revisado', 'descartado')",
                        name="chk_reporte_estado"),
        CheckConstraint("categoria IN ('ofensivo', 'datos_personales', 'spam', 'falso', 'otro')",
                        name="chk_reporte_categoria"),
        CheckConstraint("origen IN ('usuario', 'ia')", name="chk_reporte_origen"),
        CheckConstraint("origen = 'ia' OR id_usuario IS NOT NULL", name="chk_reporte_usuario"),
        UniqueConstraint("id_usuario", "id_evaluacion", name="uq_reporte_unico"),
    )

    id_reporte = Column(Integer, primary_key=True)
    id_evaluacion = Column(Integer, ForeignKey("evaluacion.id_evaluacion", ondelete="CASCADE"),
                           nullable=False)
    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario"), nullable=True)
    categoria = Column(String(30), nullable=False, default="otro")
    origen = Column(String(10), nullable=False, default="usuario")
    motivo = Column(String(300), nullable=False)
    estado = Column(String(20), nullable=False, default="pendiente")
    fecha = Column(Date, nullable=False, default=date.today)
    resuelto_por = Column(Integer, ForeignKey("usuario.id_usuario"), nullable=True)
    fecha_resolucion = Column(DateTime, nullable=True)

    evaluacion = relationship("EvaluacionORM", back_populates="reportes")
    moderador = relationship("UsuarioORM", foreign_keys=[resuelto_por])
