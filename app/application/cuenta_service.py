import secrets
from datetime import datetime, timedelta

from app.domain.cuentas.entities import (
    ESPERA_ENTRE_CODIGOS_S,
    MAX_CODIGOS_POR_HORA,
    MAX_INTENTOS_OTP,
    CodigoOtp,
    Sesion,
    Usuario,
    normalizar_correo,
)
from app.domain.cuentas.ports import EnviadorCorreo, GestorTokens, Hasher, UsuarioRepository
from app.domain.exceptions import (
    CodigoInvalido,
    CorreoNoEnviado,
    DemasiadosIntentos,
    NoAutenticado,
)


def generar_codigo():
    return f"{secrets.randbelow(1_000_000):06d}"


class CuentaService:

    def __init__(self, repo: UsuarioRepository, hasher: Hasher, tokens: GestorTokens,
                 correo: EnviadorCorreo, dominios, minutos_otp: int = 10,
                 generador=generar_codigo, reloj=datetime.now, excepciones=()):
        self.repo = repo
        self.hasher = hasher
        self.tokens = tokens
        self.correo = correo
        self.dominios = tuple(d.lower() for d in dominios)
        self.excepciones = tuple(c.lower() for c in excepciones)
        self.minutos_otp = minutos_otp
        self.generador = generador
        self.reloj = reloj

    def solicitar_codigo(self, correo):
        correo = normalizar_correo(correo, self.dominios, self.excepciones)
        usuario = self.repo.por_correo(correo)
        if usuario is None:
            usuario = self.repo.guardar(Usuario(correo_institucional=correo))
        ahora = self.reloj()
        self._revisar_limite(usuario.id_usuario, ahora)

        codigo = self.generador()
        guardado = self.repo.guardar_codigo(CodigoOtp(
            id_usuario=usuario.id_usuario,
            codigo_hash=self.hasher.hashear(codigo),
            expira=ahora + timedelta(minutes=self.minutos_otp),
            creado=ahora,
        ))
        try:
            self.correo.enviar_codigo(correo, codigo)
        except Exception as error:
            self.repo.eliminar_codigo(guardado.id_codigo)
            raise CorreoNoEnviado("No pudimos enviar el correo. Intenta de nuevo en unos minutos") from error
        return codigo

    def _revisar_limite(self, id_usuario, ahora):
        ultimo = self.repo.ultimo_codigo(id_usuario)
        if ultimo and ultimo.creado:
            pasaron = (ahora - ultimo.creado).total_seconds()
            if pasaron < ESPERA_ENTRE_CODIGOS_S:
                faltan = int(ESPERA_ENTRE_CODIGOS_S - pasaron) + 1
                raise DemasiadosIntentos(f"Ya te enviamos un código. Espera {faltan} segundos para pedir otro")
        if self.repo.contar_codigos_desde(id_usuario, ahora - timedelta(hours=1)) >= MAX_CODIGOS_POR_HORA:
            raise DemasiadosIntentos("Pediste demasiados códigos. Intenta de nuevo en una hora")

    def verificar_codigo(self, correo, codigo):
        correo = normalizar_correo(correo, self.dominios, self.excepciones)
        usuario = self.repo.por_correo(correo)
        guardado = self.repo.ultimo_codigo(usuario.id_usuario) if usuario else None
        if guardado is None or guardado.usado:
            raise CodigoInvalido("Primero solicita un código de acceso")
        if not guardado.vigente(self.reloj()):
            if guardado.intentos >= MAX_INTENTOS_OTP:
                raise DemasiadosIntentos("Demasiados intentos. Solicita un código nuevo")
            raise CodigoInvalido("El código expiró. Solicita uno nuevo")

        if not self.hasher.verificar((codigo or "").strip(), guardado.codigo_hash):
            guardado.intentos += 1
            self.repo.guardar_codigo(guardado)
            raise CodigoInvalido("El código no es correcto")

        guardado.usado = True
        self.repo.guardar_codigo(guardado)
        return self.tokens.crear(Sesion(id_usuario=usuario.id_usuario, rol=usuario.rol))

    @staticmethod
    def leer_sesion(tokens: GestorTokens, token):
        if not token:
            raise NoAutenticado("Debes iniciar sesión")
        return tokens.leer(token)
