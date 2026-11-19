from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.cuentas.entities import CodigoOtp, Usuario
from app.domain.cuentas.ports import UsuarioRepository
from app.infrastructure.db.models import CodigoOtpORM, UsuarioORM


def usuario_a_entidad(fila: UsuarioORM) -> Usuario:
    return Usuario(id_usuario=fila.id_usuario, correo_institucional=fila.correo_institucional,
                   rol=fila.rol, fecha_registro=fila.fecha_registro)


def codigo_a_entidad(fila: CodigoOtpORM) -> CodigoOtp:
    return CodigoOtp(id_codigo=fila.id_codigo, id_usuario=fila.id_usuario,
                     codigo_hash=fila.codigo_hash, expira=fila.expira,
                     intentos=fila.intentos, usado=fila.usado, creado=fila.creado)


class SqlAlchemyUsuarioRepository(UsuarioRepository):
    def __init__(self, db: Session):
        self.db = db

    def por_correo(self, correo):
        fila = self.db.query(UsuarioORM).filter_by(correo_institucional=correo).first()
        return usuario_a_entidad(fila) if fila else None

    def guardar(self, usuario):
        if usuario.id_usuario is None:
            fila = UsuarioORM(correo_institucional=usuario.correo_institucional)
            self.db.add(fila)
        else:
            fila = self.db.get(UsuarioORM, usuario.id_usuario)
        fila.rol = usuario.rol
        self.db.commit()
        self.db.refresh(fila)
        return usuario_a_entidad(fila)

    def ultimo_codigo(self, id_usuario):
        fila = (self.db.query(CodigoOtpORM).filter_by(id_usuario=id_usuario)
                .order_by(CodigoOtpORM.id_codigo.desc()).first())
        return codigo_a_entidad(fila) if fila else None

    def guardar_codigo(self, codigo):
        if codigo.id_codigo is None:
            fila = CodigoOtpORM(id_usuario=codigo.id_usuario, codigo_hash=codigo.codigo_hash,
                                expira=codigo.expira, creado=codigo.creado or datetime.now())
            self.db.add(fila)
        else:
            fila = self.db.get(CodigoOtpORM, codigo.id_codigo)
        fila.intentos = codigo.intentos
        fila.usado = codigo.usado
        self.db.commit()
        self.db.refresh(fila)
        return codigo_a_entidad(fila)

    def contar_codigos_desde(self, id_usuario, desde):
        return (self.db.query(CodigoOtpORM)
                .filter(CodigoOtpORM.id_usuario == id_usuario, CodigoOtpORM.creado >= desde)
                .count())

    def eliminar_codigo(self, id_codigo):
        fila = self.db.get(CodigoOtpORM, id_codigo)
        if fila:
            self.db.delete(fila)
            self.db.commit()
