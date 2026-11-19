import os

from dotenv import load_dotenv

load_dotenv()


def es_verdadero(valor):
    return str(valor).strip().lower() in ("1", "true", "si", "sí", "yes")


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./evaldoc.db")

CLAVE_DESARROLLO = "clave-de-desarrollo-cambiala-en-el-archivo-env"


def valor_real(nombre, por_defecto=""):
    valor = (os.getenv(nombre) or "").strip()
    return por_defecto if not valor or valor.startswith("pon_aqui") else valor


JWT_SECRETO = valor_real("JWT_SECRETO", CLAVE_DESARROLLO)
JWT_DIAS = int(os.getenv("JWT_DIAS", "120"))
OTP_MINUTOS = int(os.getenv("OTP_MINUTOS", "10"))
DOMINIOS_CORREO = [d.strip().lower() for d in
                   os.getenv("DOMINIOS_CORREO", "academia.umb.edu.co").split(",") if d.strip()]
COOKIE_SEGURA = es_verdadero(os.getenv("COOKIE_SEGURA", "false"))
MODO_DEMO = es_verdadero(os.getenv("MODO_DEMO", "true"))
ADMIN_CORREO = os.getenv("ADMIN_CORREO", "admin@umb.edu.co").strip().lower()

SMTP_SERVIDOR = os.getenv("SMTP_SERVIDOR", "")
SMTP_PUERTO = int(os.getenv("SMTP_PUERTO", "587"))
SMTP_USUARIO = os.getenv("SMTP_USUARIO", "")
SMTP_CLAVE = os.getenv("SMTP_CLAVE", "")
SMTP_REMITENTE = os.getenv("SMTP_REMITENTE", SMTP_USUARIO)

DOCENTES_POR_PAGINA = int(os.getenv("DOCENTES_POR_PAGINA", "6"))
EVALUACIONES_POR_PAGINA = int(os.getenv("EVALUACIONES_POR_PAGINA", "5"))

MODERACION_IA = es_verdadero(os.getenv("MODERACION_IA", "true"))
MODELO_MODERACION = os.getenv("MODELO_MODERACION", "gemini-3.5-flash-lite")
MODERACION_TIMEOUT_MS = int(os.getenv("MODERACION_TIMEOUT_MS", "15000"))
RUTA_PALABRAS = os.getenv("RUTA_PALABRAS", "data/palabras_prohibidas.txt")

GEMINI_API_KEY = valor_real("GEMINI_API_KEY")
RUTA_LOG_IA = os.getenv("RUTA_LOG_IA", "llamadas_ia.csv")


def problemas_de_configuracion():
    errores, avisos = [], []
    if MODO_DEMO:
        avisos.append("MODO_DEMO=true: el codigo de acceso se muestra en pantalla. Solo para pruebas y la demo.")
    else:
        if JWT_SECRETO == CLAVE_DESARROLLO or len(JWT_SECRETO) < 32:
            errores.append("JWT_SECRETO debe ser una clave propia de al menos 32 caracteres. "
                           "Genera una con: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")
        if ADMIN_CORREO == "admin@umb.edu.co":
            avisos.append("ADMIN_CORREO sigue siendo admin@umb.edu.co: en modo real el codigo llega a ese "
                          "buzon. Pon un correo tuyo para poder entrar como moderador.")
        if not SMTP_SERVIDOR:
            errores.append("Sin SMTP_SERVIDOR los codigos no llegan al correo. Configura SMTP o usa MODO_DEMO=true.")
    if SMTP_SERVIDOR and not (SMTP_USUARIO and SMTP_CLAVE):
        errores.append("Falta SMTP_USUARIO o SMTP_CLAVE.")
    if DATABASE_URL.startswith("sqlite"):
        avisos.append("Se esta usando SQLite. Para la entrega usa PostgreSQL en DATABASE_URL.")
    if MODERACION_IA and not GEMINI_API_KEY:
        avisos.append("Sin GEMINI_API_KEY la moderacion solo usa la lista de palabras.")
    return errores, avisos
