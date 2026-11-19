# EvalDoc

Proyecto final de Taller de Programación de la Universidad Manuela Beltrán (UMB), hecho por Miguel Ángel Díaz y Jhonatan Ardila.

EvalDoc es una página web donde los estudiantes de la UMB califican a sus docentes de 1 a 5 estrellas y comparten su experiencia con ellos de forma anónima. Así otros estudiantes pueden saber cómo explica un docente y cómo trata a sus estudiantes.

## Qué se puede hacer

- Buscar docentes por nombre, facultad o materia.
- Ver el perfil de un docente: promedio, cuántas personas le dieron cada calificación y sus evaluaciones.
- Iniciar sesión sin contraseña, con un código que llega al correo `@academia.umb.edu.co`.
- Calificar y comentar a un docente (una vez por materia), y editar o borrar lo que uno escribió.
- Marcar evaluaciones de otros como "Útil" y reportar las que no cumplan las normas.
- Moderar: antes de publicar un comentario lo revisan una lista de palabras y Gemini. Si parece ofensivo queda oculto hasta que un moderador lo revise.

## Tecnologías

Python, FastAPI, PostgreSQL con SQLAlchemy, plantillas Jinja2 con HTMX, bcrypt, JWT, Gemini y pytest.

## Cómo está organizado

Usamos arquitectura hexagonal, que separa el código en capas:

```
app/
  domain/          reglas del negocio (Docente, Evaluacion, Reporte, Usuario...)
  application/     casos de uso (publicar evaluación, iniciar sesión, moderar...)
  infrastructure/  base de datos, correo, cifrado y Gemini
  api/             rutas de la API, páginas web, plantillas y estilos
scripts/           carga de datos y revisión de la configuración
tests/             pruebas automáticas
docs/              guía de VS Code, diagramas UML y esquema SQL
```

El dominio no depende de ninguna otra capa. Eso lo revisa una prueba (`tests/test_arquitectura.py`).

## Cómo correrlo

La guía completa para Windows está en [docs/GUIA_VSCODE.md](docs/GUIA_VSCODE.md). En resumen:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m scripts.cargar_datos --ejemplos
python -m uvicorn app.main:app --reload
```

Después se abre http://localhost:8000. Con `MODO_DEMO=true` en el `.env`, el código de acceso aparece en la pantalla y no hace falta configurar el correo. La documentación de la API está en http://localhost:8000/docs.

## Pruebas

```
python -m pytest
```

Son 138 pruebas y cubren el 90 % del código. No necesitan internet ni PostgreSQL: usan una base de datos en memoria y simulan el correo y Gemini.
