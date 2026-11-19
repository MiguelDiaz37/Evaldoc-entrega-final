from app import config
from app.infrastructure.db.models import CodigoOtpORM
from tests.conftest import TestSession, iniciar_sesion


def un_docente(client):
    docente = client.get("/api/v1/docentes").json()[0]
    return docente["id_docente"], docente["materias"][0]["id_materia"]


def test_login_otp_completo(client, datos):
    headers = iniciar_sesion(client, "Ana.Perez@academia.umb.edu.co")
    res = client.get("/api/v1/auth/yo", headers=headers)
    assert res.status_code == 200
    assert res.json()["rol"] == "estudiante"


def test_otp_se_guarda_con_hash(client, datos):
    res = client.post("/api/v1/auth/otp/solicitar", json={"correo_institucional": "ana@academia.umb.edu.co"})
    codigo = res.json()["codigo_demo"]
    db = TestSession()
    guardado = db.query(CodigoOtpORM).first()
    db.close()
    assert guardado.codigo_hash != codigo
    assert guardado.codigo_hash.startswith("$2")


def test_otp_correo_no_institucional(client, datos):
    res = client.post("/api/v1/auth/otp/solicitar", json={"correo_institucional": "ana@gmail.com"})
    assert res.status_code == 422
    assert "academia.umb.edu.co" in res.json()["detail"]
    res = client.post("/api/v1/auth/otp/solicitar", json={"correo_institucional": "ana@umb.edu.co"})
    assert res.status_code == 422


def test_otp_codigo_incorrecto_y_reuso(client, datos):
    correo = "ana@academia.umb.edu.co"
    codigo = client.post("/api/v1/auth/otp/solicitar",
                         json={"correo_institucional": correo}).json()["codigo_demo"]
    malo = "000000" if codigo != "000000" else "111111"
    res = client.post("/api/v1/auth/otp/verificar", json={"correo_institucional": correo, "codigo": malo})
    assert res.status_code == 401

    ok = client.post("/api/v1/auth/otp/verificar", json={"correo_institucional": correo, "codigo": codigo})
    assert ok.status_code == 200
    otra_vez = client.post("/api/v1/auth/otp/verificar",
                           json={"correo_institucional": correo, "codigo": codigo})
    assert otra_vez.status_code == 401


def test_otp_bloqueo_por_intentos(client, datos):
    correo = "ana@academia.umb.edu.co"
    codigo = client.post("/api/v1/auth/otp/solicitar",
                         json={"correo_institucional": correo}).json()["codigo_demo"]
    malo = "000000" if codigo != "000000" else "111111"
    for _ in range(5):
        client.post("/api/v1/auth/otp/verificar", json={"correo_institucional": correo, "codigo": malo})
    res = client.post("/api/v1/auth/otp/verificar", json={"correo_institucional": correo, "codigo": codigo})
    assert res.status_code == 429


def test_sin_modo_demo_no_se_muestra_el_codigo(client, datos, monkeypatch):
    monkeypatch.setattr(config, "MODO_DEMO", False)
    res = client.post("/api/v1/auth/otp/solicitar", json={"correo_institucional": "ana@academia.umb.edu.co"})
    assert res.json()["codigo_demo"] is None


def test_token_invalido(client, datos):
    res = client.get("/api/v1/auth/yo", headers={"Authorization": "Bearer basura"})
    assert res.status_code == 401
    assert client.get("/api/v1/auth/yo").status_code == 401


def test_flujo_completo_de_evaluacion(client, estudiante):
    id_docente, id_materia = un_docente(client)
    res = client.post("/api/v1/evaluaciones", headers=estudiante, json={
        "id_docente": id_docente, "id_materia": id_materia, "puntaje": 4,
        "comentario": "  Explica muy bien y resuelve dudas  "})
    assert res.status_code == 201
    evaluacion = res.json()
    assert evaluacion["comentario"] == "Explica muy bien y resuelve dudas"

    perfil = client.get(f"/api/v1/docentes/{id_docente}").json()
    assert perfil["calificacion_promedio"] == 4.0
    assert len(perfil["evaluaciones"]) == 1
    assert "id_usuario" not in perfil["evaluaciones"][0]

    res = client.put(f"/api/v1/evaluaciones/{evaluacion['id_evaluacion']}", headers=estudiante,
                     json={"puntaje": 2, "comentario": None})
    assert res.status_code == 200
    assert client.get(f"/api/v1/docentes/{id_docente}").json()["calificacion_promedio"] == 2.0

    assert len(client.get("/api/v1/evaluaciones/mias", headers=estudiante).json()) == 1

    res = client.delete(f"/api/v1/evaluaciones/{evaluacion['id_evaluacion']}", headers=estudiante)
    assert res.status_code == 204
    assert client.get(f"/api/v1/docentes/{id_docente}").json()["evaluaciones"] == []


def test_evaluar_requiere_sesion(client, datos):
    id_docente, id_materia = un_docente(client)
    res = client.post("/api/v1/evaluaciones",
                      json={"id_docente": id_docente, "id_materia": id_materia, "puntaje": 4})
    assert res.status_code == 401


def test_evaluacion_duplicada(client, estudiante):
    id_docente, id_materia = un_docente(client)
    datos = {"id_docente": id_docente, "id_materia": id_materia, "puntaje": 4}
    assert client.post("/api/v1/evaluaciones", headers=estudiante, json=datos).status_code == 201
    res = client.post("/api/v1/evaluaciones", headers=estudiante, json=datos)
    assert res.status_code == 409


def test_validaciones_de_evaluacion(client, estudiante):
    id_docente, id_materia = un_docente(client)
    base = {"id_docente": id_docente, "id_materia": id_materia}
    casos = [
        ({}, 422),
        ({"puntaje": 6}, 422),
        ({"comentario": "corto"}, 422),
        ({"comentario": "x" * 501}, 422),
        ({"puntaje": "cinco"}, 422),
    ]
    for extra, esperado in casos:
        res = client.post("/api/v1/evaluaciones", headers=estudiante, json={**base, **extra})
        assert res.status_code == esperado, extra

    res = client.post("/api/v1/evaluaciones", headers=estudiante,
                      json={"id_docente": 999, "id_materia": id_materia, "puntaje": 3})
    assert res.status_code == 404
    res = client.post("/api/v1/evaluaciones", headers=estudiante,
                      json={"id_docente": id_docente, "id_materia": 999, "puntaje": 3})
    assert res.status_code == 404


def test_no_editar_evaluacion_ajena(client, estudiante, otro_estudiante):
    id_docente, id_materia = un_docente(client)
    evaluacion = client.post("/api/v1/evaluaciones", headers=estudiante, json={
        "id_docente": id_docente, "id_materia": id_materia, "puntaje": 4}).json()
    url = f"/api/v1/evaluaciones/{evaluacion['id_evaluacion']}"
    assert client.put(url, headers=otro_estudiante, json={"puntaje": 1}).status_code == 403
    assert client.delete(url, headers=otro_estudiante).status_code == 403


def test_flujo_de_moderacion(client, estudiante, otro_estudiante, admin):
    id_docente, id_materia = un_docente(client)
    evaluacion = client.post("/api/v1/evaluaciones", headers=estudiante, json={
        "id_docente": id_docente, "id_materia": id_materia,
        "comentario": "Comentario que alguien va a reportar"}).json()
    id_eval = evaluacion["id_evaluacion"]

    razon = {"id_evaluacion": id_eval, "categoria": "ofensivo",
             "motivo": "Usa un lenguaje ofensivo con el docente"}
    assert client.post("/api/v1/reportes", headers=estudiante, json=razon).status_code == 422
    sin_razon = {**razon, "motivo": "malo"}
    assert client.post("/api/v1/reportes", headers=otro_estudiante, json=sin_razon).status_code == 422
    res = client.post("/api/v1/reportes", headers=otro_estudiante, json=razon)
    assert res.status_code == 201
    assert res.json()["origen"] == "usuario"
    assert client.post("/api/v1/reportes", headers=otro_estudiante, json=razon).status_code == 409

    assert client.get("/api/v1/reportes", headers=estudiante).status_code == 403
    pendientes = client.get("/api/v1/reportes?estado=pendiente", headers=admin).json()
    assert len(pendientes) == 1
    assert pendientes[0]["evaluacion"]["comentario"] == "Comentario que alguien va a reportar"

    url = f"/api/v1/reportes/{pendientes[0]['id_reporte']}/resolver"
    assert client.post(url, headers=admin, json={"accion": "borrar"}).status_code == 422
    res = client.post(url, headers=admin, json={"accion": "ocultar"})
    assert res.json()["estado"] == "revisado"
    assert client.get(f"/api/v1/docentes/{id_docente}").json()["evaluaciones"] == []
    mias = client.get("/api/v1/evaluaciones/mias", headers=estudiante).json()
    assert mias[0]["estado"] == "oculta"
    assert client.put(f"/api/v1/evaluaciones/{id_eval}", headers=estudiante,
                      json={"puntaje": 3}).status_code == 403
    assert client.post(url, headers=admin, json={"accion": "publicar"}).status_code == 422


def test_catalogo_publico(client, datos):
    facultades = client.get("/api/v1/facultades").json()
    assert facultades[0]["nombre"] == "Facultad de Ingenierías"
    materias = client.get(f"/api/v1/materias?id_facultad={facultades[0]['id_facultad']}").json()
    assert len(materias) == 7


def test_util_una_vez_por_usuario(client, estudiante, otro_estudiante):
    id_docente, id_materia = un_docente(client)
    evaluacion = client.post("/api/v1/evaluaciones", headers=estudiante, json={
        "id_docente": id_docente, "id_materia": id_materia, "puntaje": 5}).json()
    url = f"/api/v1/evaluaciones/{evaluacion['id_evaluacion']}/util"

    assert client.post(url, headers=estudiante).status_code == 422
    assert client.post(url).status_code == 401

    res = client.post(url, headers=otro_estudiante)
    assert res.json() == {"util": True, "utiles": 1}
    res = client.post(url, headers=otro_estudiante)
    assert res.json() == {"util": False, "utiles": 0}
    client.post(url, headers=otro_estudiante)
    perfil = client.get(f"/api/v1/docentes/{id_docente}").json()
    assert perfil["evaluaciones"][0]["utiles"] == 1


def test_editar_deja_marca_de_editada(client, estudiante):
    id_docente, id_materia = un_docente(client)
    evaluacion = client.post("/api/v1/evaluaciones", headers=estudiante, json={
        "id_docente": id_docente, "id_materia": id_materia, "puntaje": 3}).json()
    assert evaluacion["fecha_edicion"] is None

    url = f"/api/v1/evaluaciones/{evaluacion['id_evaluacion']}"
    sin_cambios = client.put(url, headers=estudiante, json={"puntaje": 3}).json()
    assert sin_cambios["fecha_edicion"] is None
    editada = client.put(url, headers=estudiante, json={"puntaje": 4}).json()
    assert editada["fecha_edicion"] is not None


def test_comentario_ofensivo_queda_en_revision_y_el_admin_decide(client, estudiante, admin):
    id_docente, id_materia = un_docente(client)
    res = client.post("/api/v1/evaluaciones", headers=estudiante, json={
        "id_docente": id_docente, "id_materia": id_materia, "puntaje": 1,
        "comentario": "Es un idiota y no sabe explicar"})
    assert res.status_code == 201
    assert res.json()["estado"] == "en_revision"

    perfil = client.get(f"/api/v1/docentes/{id_docente}").json()
    assert perfil["evaluaciones"] == [] and perfil["calificacion_promedio"] is None

    reportes = client.get("/api/v1/reportes?estado=pendiente", headers=admin).json()
    assert len(reportes) == 1 and reportes[0]["origen"] == "ia"
    client.post(f"/api/v1/reportes/{reportes[0]['id_reporte']}/resolver", headers=admin,
                json={"accion": "publicar"})
    assert len(client.get(f"/api/v1/docentes/{id_docente}").json()["evaluaciones"]) == 1


def test_corregir_comentario_en_revision_lo_publica(client, estudiante, admin):
    id_docente, id_materia = un_docente(client)
    evaluacion = client.post("/api/v1/evaluaciones", headers=estudiante, json={
        "id_docente": id_docente, "id_materia": id_materia,
        "comentario": "Qué imbécil, nunca explica nada"}).json()
    res = client.put(f"/api/v1/evaluaciones/{evaluacion['id_evaluacion']}", headers=estudiante,
                     json={"comentario": "Casi nunca explica los temas con calma"})
    assert res.json()["estado"] == "publicada"
    assert client.get("/api/v1/reportes?estado=pendiente", headers=admin).json() == []


def test_limite_al_pedir_codigos(client, datos):
    correo = {"correo_institucional": "ana@academia.umb.edu.co"}
    assert client.post("/api/v1/auth/otp/solicitar", json=correo).status_code == 200
    res = client.post("/api/v1/auth/otp/solicitar", json=correo)
    assert res.status_code == 429 and "Espera" in res.json()["detail"]


def test_reporte_resuelto_guarda_moderador(client, estudiante, otro_estudiante, admin):
    id_docente, id_materia = un_docente(client)
    evaluacion = client.post("/api/v1/evaluaciones", headers=estudiante, json={
        "id_docente": id_docente, "id_materia": id_materia, "puntaje": 2}).json()
    reporte = client.post("/api/v1/reportes", headers=otro_estudiante, json={
        "id_evaluacion": evaluacion["id_evaluacion"], "categoria": "falso",
        "motivo": "Esta calificación no corresponde a la materia"}).json()
    assert reporte["resuelto_por"] is None and reporte["fecha_resolucion"] is None

    id_admin = client.get("/api/v1/auth/yo", headers=admin).json()["id_usuario"]
    res = client.post(f"/api/v1/reportes/{reporte['id_reporte']}/resolver", headers=admin,
                      json={"accion": "publicar"}).json()
    assert res["resuelto_por"] == id_admin and res["fecha_resolucion"] is not None


def test_paginacion_y_orden_en_la_api(client, datos):
    res = client.get("/api/v1/docentes?orden=nombre&pagina=2&tamano=3")
    assert len(res.json()) == 3
    assert res.headers["X-Total"] == "8" and res.headers["X-Total-Paginas"] == "3"
    assert len(client.get("/api/v1/docentes").json()) == 8
    assert client.get("/api/v1/docentes/1?orden=raro").status_code == 422
    assert client.get("/api/v1/docentes/1?orden=recientes").status_code == 200
