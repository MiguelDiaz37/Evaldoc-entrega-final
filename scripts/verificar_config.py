import sys
import time

from sqlalchemy import inspect, text

from app import config

OK, MAL, AVISO = "[ OK ]", "[FALLA]", "[AVISO]"
fallas = 0


def linea(estado, mensaje):
    global fallas
    if estado == MAL:
        fallas += 1
    print(f"{estado} {mensaje}")


def revisar_configuracion():
    print("\n1. Configuración del .env")
    errores, avisos = config.problemas_de_configuracion()
    linea(OK, f"Modo: {'DEMO (código en pantalla)' if config.MODO_DEMO else 'REAL (código por correo)'}")
    linea(OK, f"Dominios permitidos: {', '.join('@' + d for d in config.DOMINIOS_CORREO)} · admin: {config.ADMIN_CORREO}")
    for a in avisos:
        linea(AVISO, a)
    for e in errores:
        linea(MAL, e)


def revisar_base_de_datos():
    print("\n2. Base de datos")
    from app.infrastructure.db import models
    from app.infrastructure.db.database import engine
    destino = config.DATABASE_URL.split("@")[-1] if "@" in config.DATABASE_URL else config.DATABASE_URL
    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1"))
        linea(OK, f"Conexión correcta ({destino})")
    except Exception as error:
        detalle = " ".join(l.strip() for l in str(getattr(error, "orig", error)).splitlines() if l.strip())
        detalle = detalle[:220] or error.__class__.__name__
        ayuda = "Revisa que PostgreSQL esté encendido y que usuario, clave y base del DATABASE_URL existan."
        if "password authentication failed" in detalle or "autentificaci" in detalle:
            ayuda = "El usuario o la clave del DATABASE_URL no coinciden con los de PostgreSQL."
        elif "does not exist" in detalle or "no existe" in detalle:
            ayuda = "La base no existe: créala en pgAdmin (Databases > Create > Database)."
        elif "refused" in detalle.lower():
            ayuda = "PostgreSQL no está encendido (búscalo en Servicios de Windows) o el puerto no es 5432."
        linea(MAL, f"No se pudo conectar a {destino}: {detalle}. {ayuda}")
        return
    models.Base.metadata.create_all(bind=engine)
    tablas = set(inspect(engine).get_table_names())
    esperadas = {"usuario", "codigo_otp", "facultad", "materia", "docente", "docente_materia",
                 "evaluacion", "voto_util", "reporte"}
    faltan = esperadas - tablas
    if faltan:
        linea(MAL, f"Faltan tablas: {', '.join(sorted(faltan))}")
    else:
        linea(OK, "Las 9 tablas existen")
    columnas = {c["name"] for c in inspect(engine).get_columns("reporte")}
    if "resuelto_por" not in columnas:
        linea(MAL, "La tabla 'reporte' es de una versión anterior. Borra la base y créala de nuevo.")
    with engine.connect() as conexion:
        docentes = conexion.execute(text("SELECT COUNT(*) FROM docente")).scalar()
        admin = conexion.execute(text("SELECT COUNT(*) FROM usuario WHERE rol = 'admin'")).scalar()
    if docentes == 0:
        linea(AVISO, "No hay docentes cargados. Corre: python -m scripts.cargar_datos --ejemplos")
    else:
        linea(OK, f"{docentes} docentes cargados")
    if admin == 0:
        linea(AVISO, "No hay administrador. Corre el script de carga (usa ADMIN_CORREO).")


def revisar_jwt():
    print("\n3. Tokens JWT")
    from app.domain.cuentas.entities import Sesion
    from app.infrastructure.seguridad.adaptadores import JwtTokens
    if config.JWT_SECRETO == config.CLAVE_DESARROLLO:
        linea(AVISO if config.MODO_DEMO else MAL, "JWT_SECRETO es la clave de desarrollo por defecto.")
    elif len(config.JWT_SECRETO) < 32:
        linea(MAL, "JWT_SECRETO tiene menos de 32 caracteres.")
    else:
        linea(OK, f"JWT_SECRETO propio ({len(config.JWT_SECRETO)} caracteres)")
    tokens = JwtTokens(config.JWT_SECRETO, config.JWT_DIAS)
    token = tokens.crear(Sesion(id_usuario=1, rol="estudiante"))
    sesion = tokens.leer(token)
    if sesion.id_usuario == 1 and "@" not in token:
        linea(OK, f"Se crea y se lee un token (dura {config.JWT_DIAS} días, no lleva el correo)")
    else:
        linea(MAL, "El token no se pudo leer correctamente")


def revisar_gemini():
    print("\n4. Moderación con Gemini")
    if not config.MODERACION_IA:
        linea(AVISO, "MODERACION_IA=false: solo se usa la lista de palabras.")
        return
    if not config.GEMINI_API_KEY:
        linea(AVISO, "No hay GEMINI_API_KEY. Créala gratis en https://aistudio.google.com/apikey")
        return
    from app.application.moderacion_service import ModeradorIA
    from app.infrastructure.ia.gemini_client import GeminiClient
    modelo = GeminiClient(config.GEMINI_API_KEY, config.MODELO_MODERACION, config.MODERACION_TIMEOUT_MS,
                          respuesta_json=True, sin_razonamiento=True)
    ia = ModeradorIA(modelo)
    pruebas = [
        ("permitido", "Explica muy bien, aunque califica duro los parciales."),
        ("bloqueado", "Ese profesor es un inútil y un ignorante, no sirve para nada."),
        ("dudoso o bloqueado", "Vendo resúmenes de todas las materias, escríbeme al 3001234567."),
    ]
    for esperado, texto in pruebas:
        inicio = time.perf_counter()
        try:
            resultado = ia.revisar(texto)
        except Exception as error:
            nombre = error.__class__.__name__
            ayuda = {"IALimiteAlcanzado": "Se alcanzó el límite de peticiones; espera un minuto.",
                     "IATiempoAgotado": "Gemini tardó demasiado; revisa tu conexión.",
                     "IAError": "Revisa que la clave sea válida y que el modelo exista."}.get(nombre, "")
            linea(MAL, f"Gemini falló ({nombre}: {error}). {ayuda} "
                       "Ojo: si falla en la app, el comentario no se bloquea, va a revisión humana.")
            return
        ms = int((time.perf_counter() - inicio) * 1000)
        print(f"       «{texto[:48]}…» → {resultado.veredicto} ({ms} ms) · esperado: {esperado}")
    linea(OK, f"Gemini responde con el modelo {config.MODELO_MODERACION}")


def revisar_correo(destino):
    print("\n5. Envío de correo")
    if not config.SMTP_SERVIDOR:
        linea(AVISO if config.MODO_DEMO else MAL,
              "No hay SMTP_SERVIDOR: los códigos solo se escriben en la consola.")
        return
    linea(OK, f"Servidor {config.SMTP_SERVIDOR}:{config.SMTP_PUERTO} con el usuario {config.SMTP_USUARIO}")
    if not destino:
        linea(AVISO, "Para enviar un correo de prueba: python -m scripts.verificar_config --correo tu@correo")
        return
    from app.infrastructure.seguridad.adaptadores import CorreoSmtp
    correo = CorreoSmtp(config.SMTP_SERVIDOR, config.SMTP_PUERTO, config.SMTP_USUARIO,
                        config.SMTP_CLAVE, config.SMTP_REMITENTE, config.OTP_MINUTOS)
    try:
        correo.enviar_codigo(destino, "123456")
        linea(OK, f"Correo de prueba enviado a {destino} (código 123456). "
                  "Revísalo, también en correo no deseado o cuarentena.")
    except Exception as error:
        linea(MAL, f"No se pudo enviar ({error.__class__.__name__}: {error}). Con Gmail usa una "
                   "'contraseña de aplicación', no tu contraseña normal.")


if __name__ == "__main__":
    destino = sys.argv[sys.argv.index("--correo") + 1] if "--correo" in sys.argv else None
    print("Verificación de EvalDoc")
    revisar_configuracion()
    revisar_base_de_datos()
    revisar_jwt()
    revisar_gemini()
    revisar_correo(destino)
    print("\nResultado:", "todo listo." if fallas == 0 else f"{fallas} problema(s) por resolver.")
    sys.exit(1 if fallas else 0)
