def test_crud_docente_como_admin(client, admin):
    res = client.post("/api/v1/docentes", json={"nombre": "Carlos Perez"}, headers=admin)
    assert res.status_code == 201
    id_docente = res.json()["id_docente"]

    res = client.get(f"/api/v1/docentes/{id_docente}")
    assert res.status_code == 200
    assert res.json()["nombre"] == "Carlos Perez"
    assert res.json()["calificacion_promedio"] is None

    res = client.put(f"/api/v1/docentes/{id_docente}", json={"nombre": "Carlos A Perez"},
                     headers=admin)
    assert res.status_code == 200
    assert res.json()["nombre"] == "Carlos A Perez"

    res = client.delete(f"/api/v1/docentes/{id_docente}", headers=admin)
    assert res.status_code == 204
    assert client.get(f"/api/v1/docentes/{id_docente}").status_code == 404


def test_crud_docente_requiere_admin(client, estudiante):
    assert client.post("/api/v1/docentes", json={"nombre": "Carlos Perez"}).status_code == 401
    res = client.post("/api/v1/docentes", json={"nombre": "Carlos Perez"}, headers=estudiante)
    assert res.status_code == 403


def test_errores(client, admin):
    res = client.post("/api/v1/docentes", json={"nombre": "A"}, headers=admin)
    assert res.status_code == 422

    assert client.get("/api/v1/docentes/999").status_code == 404
    assert client.put("/api/v1/docentes/999", json={"nombre": "Nadie"},
                      headers=admin).status_code == 404
    assert client.delete("/api/v1/docentes/999", headers=admin).status_code == 404


def test_no_borrar_docente_con_evaluaciones(client, admin, estudiante):
    docente = client.get("/api/v1/docentes").json()[0]
    materia = docente["materias"][0]["id_materia"]
    client.post("/api/v1/evaluaciones", headers=estudiante,
                json={"id_docente": docente["id_docente"], "id_materia": materia, "puntaje": 4})

    res = client.delete(f"/api/v1/docentes/{docente['id_docente']}", headers=admin)
    assert res.status_code == 409


def test_buscar_por_nombre_facultad_y_materia(client, datos):
    assert len(client.get("/api/v1/docentes").json()) == 8
    assert [d["nombre"] for d in client.get("/api/v1/docentes?nombre=julian").json()] == [
        "Julián Castaño Mejía"
    ]

    materias = client.get("/api/v1/materias").json()
    bd = next(m for m in materias if m["nombre"] == "Bases de Datos")
    nombres = {d["nombre"] for d in client.get(f"/api/v1/docentes?id_materia={bd['id_materia']}").json()}
    assert nombres == {"Julián Castaño Mejía", "Natalia Beltrán Cruz"}

    facultad = client.get("/api/v1/facultades").json()[0]
    assert len(client.get(f"/api/v1/docentes?id_facultad={facultad['id_facultad']}").json()) == 8
    assert client.get("/api/v1/docentes?id_facultad=999").json() == []


def test_ordenar_por_calificacion(client, estudiante):
    docentes = client.get("/api/v1/docentes").json()
    notas = {docentes[0]["id_docente"]: 2, docentes[1]["id_docente"]: 5}
    for d in docentes[:2]:
        client.post("/api/v1/evaluaciones", headers=estudiante,
                    json={"id_docente": d["id_docente"], "id_materia": d["materias"][0]["id_materia"],
                          "puntaje": notas[d["id_docente"]]})

    mejor = client.get("/api/v1/docentes?orden=mejor").json()
    assert [d["calificacion_promedio"] for d in mejor[:2]] == [5.0, 2.0]
    assert mejor[2]["calificacion_promedio"] is None

    peor = client.get("/api/v1/docentes?orden=peor").json()
    assert peor[0]["calificacion_promedio"] == 2.0

    assert client.get("/api/v1/docentes?orden=raro").status_code == 422
