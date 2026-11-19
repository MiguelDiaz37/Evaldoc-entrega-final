from html import escape
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app import config
from app.application.cuenta_service import CuentaService
from app.application.docente_service import CatalogoService, DocenteService
from app.application.evaluacion_service import EvaluacionService, ReporteService
from app.container import (
    get_catalogo_service,
    get_cuenta_service,
    get_docente_service,
    get_evaluacion_service,
    get_reporte_service,
    get_sesion_opcional,
)
from app.domain.evaluacion_docente.entities import (
    CATEGORIAS_REPORTE,
    MAX_COMENTARIO,
    MAX_RAZON,
    MIN_COMENTARIO,
    MIN_RAZON,
    ordenar_evaluaciones,
    paginar,
)
from app.domain.exceptions import CorreoNoEnviado, DemasiadosIntentos, ErrorDominio

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
ETIQUETAS_NOTA = {1: "Muy malo", 2: "Malo", 3: "Regular", 4: "Bueno", 5: "Excelente"}

AVISOS = {
    "publicada": ("ok", "Tu evaluación se publicó como Estudiante anónimo."),
    "en_revision": ("alerta", "Tu evaluación quedó en revisión porque podría incumplir las "
                              "normas de la comunidad. Un moderador la revisará; mientras tanto "
                              "no se muestra."),
    "editada": ("ok", "Cambios guardados."),
    "eliminada": ("ok", "Evaluación eliminada."),
    "sesion": ("ok", "Iniciaste sesión."),
    "salio": ("ok", "Cerraste sesión."),
}


def fecha_corta(valor):
    if not valor:
        return ""
    return f"{valor.day} {MESES[valor.month - 1]} {valor.year}"


def iniciales(nombre):
    partes = [p for p in nombre.split() if p]
    return (partes[0][0] + (partes[1][0] if len(partes) > 1 else "")).upper()


templates.env.filters["fecha_corta"] = fecha_corta
templates.env.filters["iniciales"] = iniciales


def contexto(request: Request, sesion=Depends(get_sesion_opcional),
             reportes: ReporteService = Depends(get_reporte_service)):
    pendientes = reportes.contar_pendientes(sesion) if sesion and sesion.es_admin else 0
    return {"request": request, "sesion": sesion, "pendientes": pendientes,
            "aviso": AVISOS.get(request.query_params.get("aviso", "")),
            "modo_demo": config.MODO_DEMO}


def pagina(nombre, ctx, status_code=200, **extra):
    return templates.TemplateResponse(ctx["request"], nombre, {**ctx, **extra},
                                      status_code=status_code)


def a_login(request: Request):
    destino = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return RedirectResponse(f"/login?siguiente={quote(destino)}", status_code=303)


def hx_a_login(request: Request):
    pagina_actual = request.headers.get("HX-Current-URL", "/")
    return Response(status_code=204,
                    headers={"HX-Redirect": f"/login?siguiente={quote(pagina_actual)}"})


def no_encontrado(ctx, mensaje="La página que buscas no existe."):
    return pagina("web/error.html", ctx, 404, titulo="No encontrado", mensaje=mensaje)


def entero_o_none(valor):
    try:
        return int(valor) if str(valor).strip() else None
    except (TypeError, ValueError):
        return None


@router.get("/", response_class=HTMLResponse)
def inicio(ctx=Depends(contexto), q: str = "", facultad: str = "", materia: str = "",
           orden: str = "mejor", pagina_num: str = Query("1", alias="pagina"),
           docentes: DocenteService = Depends(get_docente_service),
           catalogo: CatalogoService = Depends(get_catalogo_service)):
    if orden not in ("mejor", "peor", "nombre"):
        orden = "mejor"
    id_facultad, id_materia = entero_o_none(facultad), entero_o_none(materia)
    resultado = paginar(docentes.listar(q, id_facultad, id_materia, orden),
                        entero_o_none(pagina_num) or 1, config.DOCENTES_POR_PAGINA)
    filtros = {"q": q, "facultad": id_facultad or "", "materia": id_materia or "", "orden": orden}
    datos = {
        "docentes": resultado.items, "paginacion": resultado,
        "url_pagina": "/?" + urlencode(filtros) + "&pagina=",
        "q": q, "facultad": id_facultad, "materia": id_materia, "orden": orden,
    }
    cabeceras = ctx["request"].headers
    if cabeceras.get("HX-Request") and not cabeceras.get("HX-History-Restore-Request"):
        return pagina("web/_resultados.html", ctx, **datos)
    return pagina("web/inicio.html", ctx, facultades=catalogo.facultades(),
                  materias=catalogo.materias(id_facultad), **datos)


@router.get("/docentes/{id_docente}", response_class=HTMLResponse)
def perfil(id_docente: int, ctx=Depends(contexto), materia: str = "", orden: str = "utiles",
           pagina_num: str = Query("1", alias="pagina"),
           docentes: DocenteService = Depends(get_docente_service),
           evaluaciones: EvaluacionService = Depends(get_evaluacion_service)):
    try:
        docente = docentes.obtener(id_docente)
    except ErrorDominio:
        return no_encontrado(ctx, "Ese docente no existe.")
    if orden not in ("utiles", "recientes"):
        orden = "utiles"
    id_materia = entero_o_none(materia)
    visibles = [e for e in docente.publicadas if not id_materia or e.id_materia == id_materia]
    resultado = paginar(ordenar_evaluaciones(visibles, orden), entero_o_none(pagina_num) or 1,
                        config.EVALUACIONES_POR_PAGINA)
    filtros = {"materia": id_materia or "", "orden": orden}
    sesion = ctx["sesion"]
    return pagina("web/perfil.html", ctx, docente=docente, evaluaciones=resultado.items,
                  paginacion=resultado, total_visibles=len(visibles),
                  url_pagina=f"/docentes/{id_docente}?" + urlencode(filtros) + "&pagina=",
                  materia=id_materia, orden=orden, utiles=evaluaciones.ids_utiles(sesion),
                  id_usuario=sesion.id_usuario if sesion else None,
                  categorias=CATEGORIAS_REPORTE)


@router.post("/evaluaciones/{id_evaluacion}/util", response_class=HTMLResponse)
def alternar_util(id_evaluacion: int, ctx=Depends(contexto),
                  service: EvaluacionService = Depends(get_evaluacion_service)):
    if not ctx["sesion"]:
        return hx_a_login(ctx["request"])
    try:
        marcada, total = service.alternar_util(ctx["sesion"], id_evaluacion)
    except ErrorDominio:
        return Response(status_code=204)
    return pagina("web/_boton_util.html", ctx, id_evaluacion=id_evaluacion, marcada=marcada,
                  total=total)


@router.get("/evaluaciones/{id_evaluacion}/reportar", response_class=HTMLResponse)
def form_reporte(id_evaluacion: int, ctx=Depends(contexto)):
    if not ctx["sesion"]:
        return hx_a_login(ctx["request"])
    return pagina("web/_form_reporte.html", ctx, id_evaluacion=id_evaluacion,
                  categorias=CATEGORIAS_REPORTE, categoria="ofensivo", motivo="",
                  min_razon=MIN_RAZON, max_razon=MAX_RAZON)


@router.post("/evaluaciones/{id_evaluacion}/reportar", response_class=HTMLResponse)
def enviar_reporte(id_evaluacion: int, ctx=Depends(contexto), categoria: str = Form(""),
                   motivo: str = Form(""),
                   service: ReporteService = Depends(get_reporte_service)):
    if not ctx["sesion"]:
        return hx_a_login(ctx["request"])
    try:
        service.reportar(ctx["sesion"], id_evaluacion, categoria, motivo)
    except ErrorDominio as error:
        return pagina("web/_form_reporte.html", ctx, id_evaluacion=id_evaluacion,
                      categorias=CATEGORIAS_REPORTE, categoria=categoria, motivo=motivo,
                      min_razon=MIN_RAZON, max_razon=MAX_RAZON, error=str(error))
    return pagina("web/_reporte_enviado.html", ctx)


def form_evaluacion(ctx, docente, status_code=200, **extra):
    datos = {"docente": docente, "etiquetas": ETIQUETAS_NOTA, "max_comentario": MAX_COMENTARIO,
             "min_comentario": MIN_COMENTARIO, "puntaje": None, "comentario": "",
             "id_materia": None, "editando": None, "error": None}
    datos.update(extra)
    return pagina("web/evaluar.html", ctx, status_code, **datos)


@router.get("/docentes/{id_docente}/evaluar", response_class=HTMLResponse)
def evaluar(id_docente: int, ctx=Depends(contexto), materia: str = "",
            docentes: DocenteService = Depends(get_docente_service)):
    if not ctx["sesion"]:
        return a_login(ctx["request"])
    try:
        docente = docentes.obtener(id_docente)
    except ErrorDominio:
        return no_encontrado(ctx, "Ese docente no existe.")
    return form_evaluacion(ctx, docente, id_materia=entero_o_none(materia))


@router.post("/docentes/{id_docente}/evaluar", response_class=HTMLResponse)
def publicar(id_docente: int, ctx=Depends(contexto), id_materia: str = Form(""),
             puntaje: str = Form(""), comentario: str = Form(""),
             docentes: DocenteService = Depends(get_docente_service),
             service: EvaluacionService = Depends(get_evaluacion_service)):
    if not ctx["sesion"]:
        return a_login(ctx["request"])
    try:
        docente = docentes.obtener(id_docente)
    except ErrorDominio:
        return no_encontrado(ctx, "Ese docente no existe.")
    materia, nota = entero_o_none(id_materia), entero_o_none(puntaje)
    if materia is None:
        return form_evaluacion(ctx, docente, 422, puntaje=nota, comentario=comentario,
                               error="Elige la materia en la que tuviste al docente.")
    try:
        evaluacion = service.crear(ctx["sesion"], id_docente, materia, nota, comentario or None)
    except ErrorDominio as error:
        return form_evaluacion(ctx, docente, 422, puntaje=nota, comentario=comentario,
                               id_materia=materia, error=str(error))
    aviso = "publicada" if evaluacion.publicada else "en_revision"
    return RedirectResponse(f"/docentes/{id_docente}?aviso={aviso}", status_code=303)


@router.get("/evaluaciones/{id_evaluacion}/editar", response_class=HTMLResponse)
def editar(id_evaluacion: int, ctx=Depends(contexto),
           docentes: DocenteService = Depends(get_docente_service),
           service: EvaluacionService = Depends(get_evaluacion_service)):
    if not ctx["sesion"]:
        return a_login(ctx["request"])
    try:
        evaluacion = service.obtener(id_evaluacion)
    except ErrorDominio:
        return no_encontrado(ctx)
    if not evaluacion.es_de(ctx["sesion"].id_usuario) or evaluacion.estado == "oculta":
        return no_encontrado(ctx, "No puedes editar esta evaluación.")
    return form_evaluacion(ctx, docentes.obtener(evaluacion.id_docente), editando=evaluacion,
                           puntaje=evaluacion.puntaje, comentario=evaluacion.comentario or "",
                           id_materia=evaluacion.id_materia)


@router.post("/evaluaciones/{id_evaluacion}/editar", response_class=HTMLResponse)
def guardar_edicion(id_evaluacion: int, ctx=Depends(contexto), puntaje: str = Form(""),
                    comentario: str = Form(""),
                    docentes: DocenteService = Depends(get_docente_service),
                    service: EvaluacionService = Depends(get_evaluacion_service)):
    if not ctx["sesion"]:
        return a_login(ctx["request"])
    nota = entero_o_none(puntaje)
    try:
        evaluacion = service.editar(ctx["sesion"], id_evaluacion, nota, comentario or None)
    except ErrorDominio as error:
        try:
            original = service.obtener(id_evaluacion)
        except ErrorDominio:
            return no_encontrado(ctx)
        return form_evaluacion(ctx, docentes.obtener(original.id_docente), 422,
                               editando=original, puntaje=nota, comentario=comentario,
                               id_materia=original.id_materia, error=str(error))
    aviso = "editada" if evaluacion.publicada else "en_revision"
    return RedirectResponse(f"/mis-evaluaciones?aviso={aviso}", status_code=303)


@router.post("/evaluaciones/{id_evaluacion}/eliminar")
def eliminar(id_evaluacion: int, ctx=Depends(contexto),
             service: EvaluacionService = Depends(get_evaluacion_service)):
    if not ctx["sesion"]:
        return a_login(ctx["request"])
    try:
        service.eliminar(ctx["sesion"], id_evaluacion)
    except ErrorDominio:
        return no_encontrado(ctx, "No puedes eliminar esta evaluación.")
    return RedirectResponse("/mis-evaluaciones?aviso=eliminada", status_code=303)


@router.get("/mis-evaluaciones", response_class=HTMLResponse)
def mis_evaluaciones(ctx=Depends(contexto),
                     service: EvaluacionService = Depends(get_evaluacion_service)):
    if not ctx["sesion"]:
        return a_login(ctx["request"])
    return pagina("web/mis_evaluaciones.html", ctx, evaluaciones=service.mias(ctx["sesion"]))


def destino_seguro(siguiente):
    if siguiente and siguiente.startswith("/") and not siguiente.startswith("//"):
        return siguiente
    return "/"


@router.get("/login", response_class=HTMLResponse)
def login(ctx=Depends(contexto), siguiente: str = "/"):
    if ctx["sesion"]:
        return RedirectResponse(destino_seguro(siguiente), status_code=303)
    return pagina("web/login.html", ctx, paso=1, correo="", siguiente=destino_seguro(siguiente),
                  dominios=config.DOMINIOS_CORREO)


@router.post("/login", response_class=HTMLResponse)
def pedir_codigo(ctx=Depends(contexto), correo: str = Form(""), siguiente: str = Form("/"),
                 reenvio: str = Form(""), service: CuentaService = Depends(get_cuenta_service)):
    datos = {"correo": correo, "siguiente": destino_seguro(siguiente),
             "dominios": config.DOMINIOS_CORREO}
    try:
        codigo = service.solicitar_codigo(correo)
    except DemasiadosIntentos as error:
        paso = 2 if reenvio else 1
        return pagina("web/login.html", ctx, 429, paso=paso, error=str(error),
                      minutos=config.OTP_MINUTOS, **datos)
    except CorreoNoEnviado as error:
        return pagina("web/login.html", ctx, 503, paso=1, error=str(error), **datos)
    except ErrorDominio as error:
        return pagina("web/login.html", ctx, 422, paso=1, error=str(error), **datos)
    datos["correo"] = correo.strip().lower()
    return pagina("web/login.html", ctx, paso=2,
                  codigo_demo=codigo if config.MODO_DEMO else None,
                  minutos=config.OTP_MINUTOS, **datos)


@router.post("/login/verificar", response_class=HTMLResponse)
def verificar(ctx=Depends(contexto), correo: str = Form(""), codigo: str = Form(""),
              siguiente: str = Form("/"), service: CuentaService = Depends(get_cuenta_service)):
    try:
        token = service.verificar_codigo(correo, codigo)
    except ErrorDominio as error:
        return pagina("web/login.html", ctx, 401, paso=2, correo=correo, error=str(error),
                      siguiente=destino_seguro(siguiente), minutos=config.OTP_MINUTOS,
                      dominios=config.DOMINIOS_CORREO)
    destino = destino_seguro(siguiente)
    separador = "&" if "?" in destino else "?"
    respuesta = RedirectResponse(f"{destino}{separador}aviso=sesion", status_code=303)
    # httponly: el JavaScript de la pagina no puede leer el token
    respuesta.set_cookie("token", token, max_age=config.JWT_DIAS * 24 * 3600, httponly=True,
                         samesite="lax", secure=config.COOKIE_SEGURA)
    return respuesta


@router.post("/salir")
def salir():
    respuesta = RedirectResponse("/?aviso=salio", status_code=303)
    respuesta.delete_cookie("token")
    return respuesta


@router.get("/normas", response_class=HTMLResponse)
def normas(ctx=Depends(contexto)):
    return pagina("web/normas.html", ctx)


@router.get("/privacidad", response_class=HTMLResponse)
def privacidad(ctx=Depends(contexto)):
    return pagina("web/privacidad.html", ctx, minutos=config.OTP_MINUTOS,
                  dias=config.JWT_DIAS, dominios=config.DOMINIOS_CORREO)


@router.get("/admin/reportes", response_class=HTMLResponse)
def admin_reportes(ctx=Depends(contexto), estado: str = "pendiente",
                   service: ReporteService = Depends(get_reporte_service)):
    sesion = ctx["sesion"]
    if not sesion:
        return a_login(ctx["request"])
    if not sesion.es_admin:
        return pagina("web/error.html", ctx, 403, titulo="Solo administradores",
                      mensaje="Esta sección es solo para moderadores.")
    if estado not in ("pendiente", "revisado", "descartado"):
        estado = "pendiente"
    conteo = {e: len(service.listar(sesion, e)) for e in ("pendiente", "revisado", "descartado")}
    return pagina("web/admin_reportes.html", ctx, reportes=service.listar(sesion, estado),
                  estado=estado, conteo=conteo)


@router.post("/admin/reportes/{id_reporte}/resolver", response_class=HTMLResponse)
def resolver(id_reporte: int, ctx=Depends(contexto), accion: str = Form(""),
             service: ReporteService = Depends(get_reporte_service)):
    sesion = ctx["sesion"]
    if not sesion:
        return hx_a_login(ctx["request"])
    try:
        reporte = service.resolver(sesion, id_reporte, accion)
    except ErrorDominio as error:
        return HTMLResponse(f'<p class="error-linea" role="alert">{escape(str(error))}</p>')
    return pagina("web/_tarjeta_reporte.html", ctx, r=reporte, recien_resuelto=True,
                  pendientes=service.contar_pendientes(sesion))
