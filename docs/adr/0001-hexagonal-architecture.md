# ADR 0001: Arquitectura hexagonal

- Estado: Aceptada
- Fecha: 2026-10-31 (actualizada el 2026-11-16)
- Autores: Miguel Díaz, Jhonatan Ardila

## Contexto

La primera versión de EvalDoc mezclaba en los mismos archivos el manejo de HTTP, las consultas de SQLAlchemy y las reglas de negocio. Eso causaba tres problemas:

1. Reglas como "un docente con evaluaciones no se puede eliminar" o "una evaluación por docente y materia" vivían dentro de los controladores HTTP, y la única forma de probarlas era a través de la API y con base de datos.
2. La moderación de comentarios necesita un modelo de IA externo (Gemini). Si el cliente se crea dentro del controlador, las pruebas no lo pueden reemplazar y cada prueba gastaría la API.
3. La aplicación tiene dos formas de entrada (la API REST y las páginas web) que deben aplicar exactamente las mismas reglas.

## Decisión

El código se divide en cuatro capas siguiendo puertos y adaptadores:

| Capa | Paquete | Depende de |
|---|---|---|
| Dominio | `app/domain` | nada (Python puro) |
| Aplicación (casos de uso) | `app/application` | dominio |
| Adaptadores de entrada | `app/api` | aplicación, dominio |
| Adaptadores de salida | `app/infrastructure` | dominio |

El dominio tiene tres contextos: `evaluacion_docente`, `cuentas` e `ia`. Define los puertos como clases abstractas (`DocenteRepository`, `EvaluacionRepository`, `ReporteRepository`, `UsuarioRepository`, `Moderador`, `ModeloIA`, `Hasher`, `GestorTokens`, `EnviadorCorreo`). La infraestructura los implementa con SQLAlchemy, Gemini, bcrypt, PyJWT y SMTP.

Los casos de uso reciben sus puertos por el constructor (`EvaluacionService(evaluaciones, docentes, catalogo, reportes, moderador)`). `app/container.py` arma las dependencias para FastAPI. La API REST y las páginas web llaman a los mismos casos de uso.

## Consecuencias

- Las reglas de negocio se prueban sin base de datos ni red, con objetos simulados (`unittest.mock`).
- La moderación se prueba sin gastar la API de Gemini, y si Gemini falla el caso de uso no se entera: recibe un veredicto "dudoso" y el comentario va a revisión humana.
- Cambiar de base de datos, de proveedor de IA o de servidor de correo solo afecta a la infraestructura.
- Hay más archivos y clases que en la primera versión. Para el tamaño de este proyecto es un costo aceptable.
- `tests/test_arquitectura.py` revisa automáticamente que el dominio no importe otras capas ni librerías externas.
