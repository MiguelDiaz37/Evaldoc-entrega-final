from datetime import datetime, timedelta

import pytest

from app.domain.cuentas.entities import CodigoOtp, normalizar_correo
from app.domain.evaluacion_docente.entities import (
    Docente,
    Evaluacion,
    Materia,
    Reporte,
    filtrar_por_nombre,
    ordenar_docentes,
    ordenar_evaluaciones,
    paginar,
)
from app.domain.exceptions import CorreoNoInstitucional, DatoInvalido


def test_evaluacion_solo_con_puntaje():
    assert Evaluacion(puntaje=4).comentario is None


def test_evaluacion_solo_con_comentario():
    assert Evaluacion(comentario="Explica muy bien los temas").puntaje is None


def test_evaluacion_vacia_no_se_permite():
    with pytest.raises(DatoInvalido):
        Evaluacion()


def test_comentario_solo_espacios_cuenta_como_vacio():
    with pytest.raises(DatoInvalido):
        Evaluacion(comentario="     ")


@pytest.mark.parametrize("puntaje", [0, 6, -1])
def test_puntaje_fuera_de_rango(puntaje):
    with pytest.raises(DatoInvalido):
        Evaluacion(puntaje=puntaje)


@pytest.mark.parametrize("puntaje", [1, 5])
def test_puntaje_en_los_limites(puntaje):
    assert Evaluacion(puntaje=puntaje).puntaje == puntaje


def test_comentario_muy_corto_o_muy_largo():
    with pytest.raises(DatoInvalido):
        Evaluacion(comentario="malo")
    with pytest.raises(DatoInvalido):
        Evaluacion(comentario="a" * 501)
    assert len(Evaluacion(comentario="a" * 500).comentario) == 500


def test_actualizar_valida_de_nuevo():
    evaluacion = Evaluacion(puntaje=3)
    with pytest.raises(DatoInvalido):
        evaluacion.actualizar(None, "", datetime(2026, 11, 16))


def test_actualizar_marca_editada_solo_si_cambia():
    evaluacion = Evaluacion(puntaje=3, comentario="Explica bien los temas")
    assert not evaluacion.actualizar(3, " Explica bien los temas ", datetime(2026, 11, 16))
    assert not evaluacion.editada
    assert evaluacion.actualizar(4, "Explica bien los temas", datetime(2026, 11, 16))
    assert evaluacion.editada


def test_promedio_ignora_evaluaciones_sin_puntaje():
    docente = Docente(nombre="Laura Gomez", evaluaciones=[
        Evaluacion(puntaje=5), Evaluacion(puntaje=4),
        Evaluacion(comentario="Sin nota pero con comentario"),
    ])
    assert docente.calificacion_promedio == 4.5
    assert docente.total_calificaciones == 2


def test_promedio_y_perfil_ignoran_evaluaciones_no_publicadas():
    docente = Docente(nombre="Laura Gomez", evaluaciones=[
        Evaluacion(puntaje=5), Evaluacion(puntaje=1, estado="en_revision"),
        Evaluacion(puntaje=1, estado="oculta"),
    ])
    assert docente.calificacion_promedio == 5.0
    assert len(docente.publicadas) == 1
    assert docente.distribucion == {5: 1, 4: 0, 3: 0, 2: 0, 1: 0}
    assert not docente.puede_eliminarse()


def test_promedio_sin_calificaciones_es_none():
    assert Docente(nombre="Laura Gomez").calificacion_promedio is None


def test_dicta_materia():
    docente = Docente(nombre="Laura Gomez", materias=[Materia("Bases de Datos", 1, id_materia=3)])
    assert docente.dicta(3)
    assert not docente.dicta(4)


def test_ordenar_docentes():
    a = Docente(nombre="Beatriz", evaluaciones=[Evaluacion(puntaje=2)])
    b = Docente(nombre="Andres", evaluaciones=[Evaluacion(puntaje=5)])
    c = Docente(nombre="Camilo")
    assert [d.nombre for d in ordenar_docentes([a, b, c], "nombre")] == ["Andres", "Beatriz", "Camilo"]
    assert [d.nombre for d in ordenar_docentes([a, b, c], "mejor")] == ["Andres", "Beatriz", "Camilo"]
    assert [d.nombre for d in ordenar_docentes([a, b, c], "peor")] == ["Beatriz", "Andres", "Camilo"]
    with pytest.raises(DatoInvalido):
        ordenar_docentes([a], "otro")


def test_busqueda_ignora_tildes_y_mayusculas():
    docentes = [Docente(nombre="Julián Castaño"), Docente(nombre="Andrea Rincón")]
    assert [d.nombre for d in filtrar_por_nombre(docentes, "JULIAN castano")] == ["Julián Castaño"]
    assert len(filtrar_por_nombre(docentes, "  ")) == 2


def test_reporte_motivo_y_estado():
    with pytest.raises(DatoInvalido):
        Reporte(id_evaluacion=1, id_usuario=1, categoria="ofensivo", motivo="mal")
    with pytest.raises(DatoInvalido):
        Reporte(id_evaluacion=1, id_usuario=1, categoria="inventada", motivo="Contiene insultos")
    reporte = Reporte(id_evaluacion=1, id_usuario=1, categoria="ofensivo", motivo="Contiene insultos")
    assert reporte.nombre_categoria == "Lenguaje ofensivo o insultos"
    assert reporte.estado == "pendiente"
    reporte.cambiar_estado("revisado")
    with pytest.raises(DatoInvalido):
        reporte.cambiar_estado("borrado")


DOMINIOS = ("academia.umb.edu.co",)


@pytest.mark.parametrize("correo", ["Ana.Perez@ACADEMIA.umb.edu.co", "luis@academia.umb.edu.co"])
def test_correos_de_estudiante_validos(correo):
    assert normalizar_correo(correo, DOMINIOS) == correo.lower()


@pytest.mark.parametrize("correo", ["ana@gmail.com", "ana@umb.edu.co", "ana@x.academia.umb.edu.co",
                                    "ana@academia.umb.edu.co.com", "sin-arroba", "", None,
                                    "ana@fakeacademia.umb.edu.co"])
def test_correos_no_permitidos(correo):
    with pytest.raises(CorreoNoInstitucional):
        normalizar_correo(correo, DOMINIOS)


def test_correo_del_admin_es_excepcion():
    assert normalizar_correo("Admin@umb.edu.co", DOMINIOS, ("admin@umb.edu.co",)) == "admin@umb.edu.co"


def test_codigo_otp_vigencia():
    ahora = datetime(2026, 11, 16, 12, 0)
    codigo = CodigoOtp(id_usuario=1, codigo_hash="x", expira=ahora + timedelta(minutes=10))
    assert codigo.vigente(ahora)
    assert not codigo.vigente(ahora + timedelta(minutes=11))
    codigo.intentos = 5
    assert not codigo.vigente(ahora)


def test_ordenar_evaluaciones_por_utiles_y_por_fecha():
    from datetime import date
    vieja_util = Evaluacion(puntaje=3, id_evaluacion=1, fecha=date(2026, 9, 1), utiles=7)
    nueva = Evaluacion(puntaje=4, id_evaluacion=2, fecha=date(2026, 11, 1), utiles=0)
    media = Evaluacion(puntaje=5, id_evaluacion=3, fecha=date(2026, 10, 1), utiles=0)
    assert [e.id_evaluacion for e in ordenar_evaluaciones([nueva, vieja_util, media])] == [1, 2, 3]
    assert [e.id_evaluacion for e in ordenar_evaluaciones([vieja_util, media, nueva], "recientes")] == [2, 3, 1]
    with pytest.raises(DatoInvalido):
        ordenar_evaluaciones([], "raro")


def test_paginar():
    numeros = list(range(1, 14))
    pagina = paginar(numeros, 2, 5)
    assert pagina.items == [6, 7, 8, 9, 10]
    assert (pagina.total, pagina.total_paginas, pagina.anterior, pagina.siguiente) == (13, 3, 1, 3)
    assert paginar(numeros, 3, 5).items == [11, 12, 13] and paginar(numeros, 3, 5).siguiente is None
    assert paginar(numeros, 99, 5).pagina == 3
    assert paginar(numeros, -4, 5).pagina == 1
    vacia = paginar([], 1, 5)
    assert (vacia.items, vacia.total_paginas) == ([], 1)


def test_cerrar_reporte_guarda_quien_y_cuando():
    reporte = Reporte(id_evaluacion=1, id_usuario=2, categoria="spam", motivo="Es publicidad")
    reporte.cerrar("revisado", datetime(2026, 11, 16, 15, 0), id_moderador=9)
    assert (reporte.estado, reporte.resuelto_por) == ("revisado", 9)
    with pytest.raises(DatoInvalido):
        reporte.cerrar("pendiente", datetime(2026, 11, 16))
