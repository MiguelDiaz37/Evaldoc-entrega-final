# Guía para correr EvalDoc en VS Code (Windows)

## 1. Instalar los programas

- Python 3.12 o más nuevo, desde python.org. Al instalar, marca la casilla "Add python.exe to PATH".
- PostgreSQL, desde postgresql.org/download. Anota la clave que le pongas al usuario `postgres`.
- VS Code, desde code.visualstudio.com.

## 2. Crear la base de datos

Abre SQL Shell (psql), que viene con PostgreSQL. Presiona Enter en todas las preguntas, escribe la clave de `postgres` y luego:

```sql
CREATE USER evaldoc WITH PASSWORD 'evaldoc';
CREATE DATABASE evaldoc OWNER evaldoc;
\q
```

## 3. Abrir el proyecto

1. En VS Code ve a File, Open Folder y elige la carpeta `evaldoc`.
2. Abre una terminal con Terminal, New Terminal, y escribe:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Si sale el error "running scripts is disabled", escribe `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a activar el entorno.

## 4. Revisar el .env

El `.env` que copiaste ya sirve para probar. Lo que más se cambia es:

- `DATABASE_URL`: el usuario, la clave y la base que creaste en el paso 2.
- `MODO_DEMO=true`: el código de acceso sale en pantalla, sin necesidad de correo.
- `ADMIN_CORREO`: el correo con el que entras como moderador.
- `GEMINI_API_KEY`: la clave de aistudio.google.com/apikey. Sin ella la moderación solo usa la lista de palabras.

## 5. Cargar los datos y arrancar

```powershell
python -m scripts.cargar_datos --ejemplos
python -m uvicorn app.main:app --reload
```

Abre http://localhost:8000. Para entrar usa un correo que termine en `@academia.umb.edu.co`. Para entrar como moderador, usa el correo de `ADMIN_CORREO`.

## 6. Correr las pruebas

```powershell
python -m pytest
```

Deben pasar las 138.

## 7. Usarlo con correo real

Para que el código llegue al correo en vez de salir en pantalla:

1. Genera una clave para los tokens y ponla en `JWT_SECRETO`:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. En una cuenta de Gmail activa la verificación en dos pasos y crea una contraseña de aplicación en myaccount.google.com/apppasswords.
3. Llena en el `.env`: `SMTP_SERVIDOR=smtp.gmail.com`, `SMTP_PUERTO=587`, tu Gmail en `SMTP_USUARIO` y `SMTP_REMITENTE`, y la contraseña de aplicación (sin espacios) en `SMTP_CLAVE`.
4. Cambia `MODO_DEMO=false` y vuelve a correr `python -m scripts.cargar_datos`.
5. Revisa que todo funcione:
   `python -m scripts.verificar_config --correo tu.correo@academia.umb.edu.co`

Si el correo no llega, búscalo en correo no deseado.

## Problemas comunes

- "password authentication failed": el usuario o la clave del `DATABASE_URL` no coinciden con los de PostgreSQL.
- "ModuleNotFoundError": falta activar el entorno (`venv\Scripts\activate`).
- "Fatal error in launcher": moviste la carpeta después de crear el `venv`. Bórralo y créalo otra vez (paso 3).
- El puerto 8000 está ocupado: usa `python -m uvicorn app.main:app --reload --port 8001`.
