import re

from app import config


def entrar(client, correo, siguiente="/"):
    res = client.post("/login", data={"correo": correo, "siguiente": siguiente})
    codigo = re.search(r"tu código es (\d{6})", res.text).group(1)
    return client.post("/login/verificar", data={"correo": correo, "codigo": codigo,
                                                 "siguiente": siguiente}, follow_redirects=False)


def test_inicio_y_busqueda_parcial_con_htmx(client, datos):
    res = client.get("/")
    assert res.status_code == 200
    assert "Conoce a tus docentes" in res.text and "<html" in res.text

    parcial = client.get("/?q=julian", headers={"HX-Request": "true"})
    assert "<html" not in parcial.text
    assert "Julián Castaño Mejía" in parcial.text and "Andrea" not in parcial.text


def test_paginas_privadas_piden_sesion(client, datos):
    for ruta in ("/mis-evaluaciones", "/docentes/1/evaluar", "/admin/reportes"):
        res = client.get(ruta, follow_redirects=False)
        assert res.status_code == 303 and res.headers["location"].startswith("/login?siguiente=")


def test_login_deja_cookie_httponly_y_redirige(client, datos):
    res = entrar(client, "ana@academia.umb.edu.co", "/mis-evaluaciones")
    assert res.status_code == 303
    assert res.headers["location"] == "/mis-evaluaciones?aviso=sesion"
    cookie = res.headers["set-cookie"].lower()
    assert "token=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/mis-evaluaciones").status_code == 200


def test_login_no_redirige_a_otros_sitios(client, datos):
    res = entrar(client, "ana@academia.umb.edu.co", "//sitio-malicioso.com")
    assert res.headers["location"].startswith("/?")


def test_login_con_correo_no_permitido_muestra_error(client, datos):
    res = client.post("/login", data={"correo": "ana@umb.edu.co", "siguiente": "/"})
    assert res.status_code == 422
    assert "academia.umb.edu.co" in res.text


def test_publicar_desde_el_formulario(client, datos):
    entrar(client, "ana@academia.umb.edu.co")
    docente = client.get("/api/v1/docentes").json()[0]
    url = f"/docentes/{docente['id_docente']}/evaluar"
    datos_form = {"id_materia": docente["materias"][0]["id_materia"], "puntaje": "5",
                  "comentario": "Explica muy bien y con paciencia"}

    res = client.post(url, data=datos_form, follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"].endswith("aviso=publicada")

    repetida = client.post(url, data=datos_form)
    assert repetida.status_code == 422 and "Ya evaluaste" in repetida.text

    ofensiva = client.post(url, data={**datos_form, "id_materia": docente["materias"][-1]["id_materia"],
                                      "comentario": "Es un idiota total"}, follow_redirects=False)
    if docente["materias"][-1]["id_materia"] != docente["materias"][0]["id_materia"]:
        assert ofensiva.headers["location"].endswith("aviso=en_revision")


def test_util_por_htmx_sin_sesion_manda_al_login(client, datos):
    res = client.post("/evaluaciones/1/util", headers={"HX-Request": "true",
                                                       "HX-Current-URL": "http://x/docentes/1"})
    assert res.status_code == 204 and res.headers["HX-Redirect"].startswith("/login")


def test_moderacion_solo_para_admin(client, datos):
    entrar(client, "ana@academia.umb.edu.co")
    assert client.get("/admin/reportes").status_code == 403
    client.post("/salir")
    entrar(client, config.ADMIN_CORREO)
    assert client.get("/admin/reportes").status_code == 200


def test_paginas_de_normas_y_privacidad(client, datos):
    normas = client.get("/normas")
    assert normas.status_code == 200 and "moderador humano" in normas.text
    privacidad = client.get("/privacidad")
    assert privacidad.status_code == 200 and "Ley 1581" in privacidad.text
    assert 'href="/normas"' in client.get("/").text


def test_inicio_paginado(client, datos):
    primera = client.get("/", headers={"HX-Request": "true"})
    assert primera.text.count('class="tarjeta docente"') == config.DOCENTES_POR_PAGINA
    assert "página 1 de 2" in primera.text
    segunda = client.get("/?pagina=2", headers={"HX-Request": "true"})
    assert segunda.text.count('class="tarjeta docente"') == 8 - config.DOCENTES_POR_PAGINA


def test_reenviar_codigo_muy_rapido_se_queda_en_el_paso_dos(client, datos):
    client.post("/login", data={"correo": "ana@academia.umb.edu.co", "siguiente": "/"})
    res = client.post("/login", data={"correo": "ana@academia.umb.edu.co", "siguiente": "/",
                                      "reenvio": "1"})
    assert res.status_code == 429
    assert "Espera" in res.text and 'name="codigo"' in res.text
