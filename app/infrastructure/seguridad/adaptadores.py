import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr

import bcrypt
import jwt

from app.domain.cuentas.entities import Sesion
from app.domain.cuentas.ports import EnviadorCorreo, GestorTokens, Hasher
from app.domain.exceptions import NoAutenticado

log = logging.getLogger("evaldoc.correo")


class BcryptHasher(Hasher):
    def hashear(self, texto):
        return bcrypt.hashpw(texto.encode(), bcrypt.gensalt()).decode()

    def verificar(self, texto, hash_guardado):
        try:
            return bcrypt.checkpw(texto.encode(), hash_guardado.encode())
        except ValueError:
            return False


class JwtTokens(GestorTokens):
    def __init__(self, secreto, dias):
        self.secreto = secreto
        self.dias = dias

    def crear(self, sesion):
        ahora = datetime.now(timezone.utc)
        datos = {"sub": str(sesion.id_usuario), "rol": sesion.rol, "iat": ahora,
                 "exp": ahora + timedelta(days=self.dias)}
        return jwt.encode(datos, self.secreto, algorithm="HS256")

    def leer(self, token):
        try:
            datos = jwt.decode(token, self.secreto, algorithms=["HS256"])
            return Sesion(id_usuario=int(datos["sub"]), rol=datos["rol"])
        except jwt.ExpiredSignatureError:
            raise NoAutenticado("Tu sesión expiró, vuelve a iniciar sesión")
        except (jwt.InvalidTokenError, KeyError, ValueError):
            raise NoAutenticado("Sesión inválida, vuelve a iniciar sesión")


class CorreoConsola(EnviadorCorreo):

    def enviar_codigo(self, correo, codigo):
        log.warning("Codigo OTP para %s: %s", correo, codigo)


class CorreoSmtp(EnviadorCorreo):

    def __init__(self, servidor, puerto, usuario, clave, remitente, minutos=10):
        self.servidor = servidor
        self.puerto = puerto
        self.usuario = usuario
        self.clave = clave
        self.remitente = remitente
        self.minutos = minutos

    def armar_mensaje(self, correo, codigo):
        mensaje = EmailMessage()
        mensaje["Subject"] = f"{codigo} es tu código de acceso a EvalDoc"
        mensaje["From"] = formataddr(("EvalDoc", self.remitente))
        mensaje["To"] = correo
        mensaje.set_content(
            f"Tu código de acceso a EvalDoc es: {codigo}\n\n"
            f"Vence en {self.minutos} minutos y solo sirve una vez.\n"
            "Si no lo pediste, ignora este correo: nadie puede entrar sin el código.\n"
        )
        mensaje.add_alternative(f"""\
<div style="font-family: Arial, sans-serif; max-width: 460px; margin: auto; color: #1A2233">
  <h2 style="color: #1E3A8A; margin-bottom: 4px">EvalDoc</h2>
  <p>Tu código de acceso es:</p>
  <p style="font-size: 32px; font-weight: bold; letter-spacing: 8px; background: #EEF2FF;
            padding: 14px; text-align: center; border-radius: 10px">{codigo}</p>
  <p>Vence en {self.minutos} minutos y solo sirve una vez.</p>
  <p style="color: #5B6474; font-size: 13px">Si no lo pediste, ignora este correo:
     nadie puede entrar sin el código.</p>
</div>""", subtype="html")
        return mensaje

    def enviar_codigo(self, correo, codigo):
        mensaje = self.armar_mensaje(correo, codigo)
        if self.puerto == 465:
            with smtplib.SMTP_SSL(self.servidor, self.puerto, timeout=15) as smtp:
                smtp.login(self.usuario, self.clave)
                smtp.send_message(mensaje)
        else:
            with smtplib.SMTP(self.servidor, self.puerto, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(self.usuario, self.clave)
                smtp.send_message(mensaje)
