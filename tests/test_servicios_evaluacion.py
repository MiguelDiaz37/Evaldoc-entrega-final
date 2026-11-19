from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from app.application.cuenta_service import CuentaService
from app.application.evaluacion_service import EvaluacionService, ReporteService
from app.domain.cuentas.entities import CodigoOtp, Sesion, Usuario
from app.domain.cuentas.ports import EnviadorCorreo, GestorTokens, Hasher, UsuarioRepository
from app.domain.evaluacion_docente.entities import (
    Docente,
    Evaluacion,
    Materia,
    Reporte,
    ResultadoModeracion,
)
from app.domain.evaluacion_docente.ports import (
    CatalogoRepository,
    DocenteRepository,
    EvaluacionRepository,
    Moderador,
    ReporteRepository,
)
from app.domain.exceptions import (
    CodigoInvalido,
    DatoInvalido,
    DemasiadosIntentos,
    DocenteNoEncontrado,
    EvaluacionDuplicada,
    MateriaNoEncontrada,
    ReporteDuplicado,
    SinPermiso,
)

ESTUDIANTE = Sesion(id_usuario=1, rol="estudiante")
OTRO = Sesion(id_usuario=2, rol="estudiante")
ADMIN = Sesion(id_usuario=9, rol="admin")
BD = Materia("Bases de Datos", 1, id_materia=3)
AHORA = datetime(2026, 11, 16, 12, 0)


def con_id(evaluacion):
    if evaluacion.id_evaluacion is None:
        evaluacion.id_evaluacion = 5
    return evaluacion


@pytest.fixture
def mocks():
    evaluaciones = Mock(spec=EvaluacionRepository)
    docentes = Mock(spec=DocenteRepository)
    catalogo = Mock(spec=CatalogoRepository)
    reportes = Mock(spec=ReporteRepository)
    moderador = Mock(spec=Moderador)
    docentes.obtener.return_value = Docente(id_docente=1, nombre="Laura Gomez", materias=[BD])
    catalogo.obtener_materia.return_value = BD
    evaluaciones.existe.return_value = False
    evaluaciones.guardar.side_effect = con_id
    reportes.pendientes_de.return_value = []
    moderador.revisar.return_value = ResultadoModeracion("permitido")
    return evaluaciones, docentes, catalogo, reportes, moderador


def servicio(mocks):
    return EvaluacionService(*mocks, reloj=lambda: AHORA)


def test_crear_evaluacion_ok(mocks):
    evaluacion = servicio(mocks).crear(ESTUDIANTE, 1, 3, puntaje=4)
    assert evaluacion.id_usuario == 1
    assert evaluacion.estado == "publicada"
    mocks[0].guardar.assert_called_once()
    mocks[3].guardar.assert_not_called()


def test_crear_evaluacion_duplicada(mocks):
    mocks[0].existe.return_value = True
    with pytest.raises(EvaluacionDuplicada):
        servicio(mocks).crear(ESTUDIANTE, 1, 3, puntaje=4)
    mocks[0].guardar.assert_not_called()


def test_crear_evaluacion_docente_o_materia_inexistente(mocks):
    mocks[1].obtener.return_value = None
    with pytest.raises(DocenteNoEncontrado):
        servicio(mocks).crear(ESTUDIANTE, 99, 3, puntaje=4)

    mocks[1].obtener.return_value = Docente(id_docente=1, nombre="Laura Gomez", materias=[BD])
    mocks[2].obtener_materia.return_value = None
    with pytest.raises(MateriaNoEncontrada):
        servicio(mocks).crear(ESTUDIANTE, 1, 99, puntaje=4)


def test_crear_evaluacion_materia_que_no_dicta(mocks):
    mocks[2].obtener_materia.return_value = Materia("Cálculo", 1, id_materia=8)
    with pytest.raises(DatoInvalido):
        servicio(mocks).crear(ESTUDIANTE, 1, 8, puntaje=4)


def test_comentario_bloqueado_queda_en_revision_con_reporte_automatico(mocks):
    mocks[4].revisar.return_value = ResultadoModeracion("bloqueado", "Insulta al docente")
    evaluacion = servicio(mocks).crear(ESTUDIANTE, 1, 3, comentario="Comentario con insultos")
    assert evaluacion.estado == "en_revision"
    reporte = mocks[3].guardar.call_args.args[0]
    assert reporte.origen == "ia" and reporte.id_usuario is None
    assert reporte.categoria == "ofensivo"
    assert "Insulta al docente" in reporte.motivo


def test_comentario_dudoso_se_publica_pero_con_reporte(mocks):
    mocks[4].revisar.return_value = ResultadoModeracion("dudoso", "Posible spam")
    evaluacion = servicio(mocks).crear(ESTUDIANTE, 1, 3, comentario="Vendo resúmenes baratos")
    assert evaluacion.estado == "publicada"
    assert mocks[3].guardar.call_args.args[0].origen == "ia"


def test_solo_estrellas_no_llama_a_la_ia_con_texto(mocks):
    servicio(mocks).crear(ESTUDIANTE, 1, 3, puntaje=5)
    mocks[4].revisar.assert_called_once_with(None)


def test_editar_marca_fecha_y_vuelve_a_moderar(mocks):
    mocks[0].obtener.return_value = Evaluacion(id_evaluacion=5, id_usuario=1, puntaje=3)
    evaluacion = servicio(mocks).editar(ESTUDIANTE, 5, puntaje=4, comentario="Mejoró bastante")
    assert evaluacion.fecha_edicion == AHORA
    mocks[4].revisar.assert_called_once_with("Mejoró bastante")


def test_editar_sin_cambios_no_marca_editada(mocks):
    mocks[0].obtener.return_value = Evaluacion(id_evaluacion=5, id_usuario=1, puntaje=3)
    evaluacion = servicio(mocks).editar(ESTUDIANTE, 5, puntaje=3)
    assert evaluacion.fecha_edicion is None
    mocks[0].guardar.assert_not_called()


def test_corregir_un_comentario_en_revision_lo_publica_y_cierra_el_reporte_de_la_ia(mocks):
    mocks[0].obtener.return_value = Evaluacion(id_evaluacion=5, id_usuario=1, estado="en_revision",
                                               comentario="Texto que la IA bloqueó")
    reporte_ia = Reporte(id_reporte=7, id_evaluacion=5, categoria="ofensivo",
                         motivo="Oculta hasta revisión: insultos", origen="ia")
    mocks[3].pendientes_de.return_value = [reporte_ia]

    evaluacion = servicio(mocks).editar(ESTUDIANTE, 5, comentario="Texto corregido y respetuoso")

    assert evaluacion.estado == "publicada"
    assert mocks[3].guardar.call_args.args[0].estado == "descartado"


def test_no_se_edita_una_evaluacion_oculta_por_el_moderador(mocks):
    mocks[0].obtener.return_value = Evaluacion(id_evaluacion=5, id_usuario=1, puntaje=1,
                                               estado="oculta")
    with pytest.raises(SinPermiso):
        servicio(mocks).editar(ESTUDIANTE, 5, puntaje=2)


def test_editar_y_eliminar_solo_el_dueno(mocks):
    mocks[0].obtener.return_value = Evaluacion(id_evaluacion=5, id_usuario=1, puntaje=3)
    service = servicio(mocks)

    with pytest.raises(SinPermiso):
        service.editar(OTRO, 5, puntaje=1)
    with pytest.raises(SinPermiso):
        service.eliminar(OTRO, 5)

    assert service.editar(ESTUDIANTE, 5, puntaje=5).puntaje == 5
    service.eliminar(ADMIN, 5)
    mocks[0].eliminar.assert_called_once_with(5)


def test_util_marca_y_desmarca(mocks):
    mocks[0].obtener.return_value = Evaluacion(id_evaluacion=5, id_usuario=1, puntaje=3, utiles=0)
    mocks[0].marco_util.return_value = False
    assert servicio(mocks).alternar_util(OTRO, 5)[0] is True
    mocks[0].marcar_util.assert_called_once_with(2, 5)

    mocks[0].marco_util.return_value = True
    assert servicio(mocks).alternar_util(OTRO, 5)[0] is False
    mocks[0].quitar_util.assert_called_once_with(2, 5)


def test_util_no_en_la_propia_ni_en_ocultas(mocks):
    mocks[0].obtener.return_value = Evaluacion(id_evaluacion=5, id_usuario=1, puntaje=3)
    with pytest.raises(DatoInvalido):
        servicio(mocks).alternar_util(ESTUDIANTE, 5)
    mocks[0].obtener.return_value = Evaluacion(id_evaluacion=5, id_usuario=1, puntaje=3,
                                               estado="oculta")
    with pytest.raises(Exception):
        servicio(mocks).alternar_util(OTRO, 5)


def test_reportes():
    reportes = Mock(spec=ReporteRepository)
    evaluaciones = Mock(spec=EvaluacionRepository)
    evaluaciones.obtener.return_value = Evaluacion(id_evaluacion=5, id_usuario=1, puntaje=1)
    reportes.existe.return_value = False
    reportes.guardar.side_effect = lambda r: r
    service = ReporteService(reportes, evaluaciones)

    with pytest.raises(DatoInvalido):
        service.reportar(ESTUDIANTE, 5, "ofensivo", "Mi propia evaluación")
    reporte = service.reportar(OTRO, 5, "ofensivo", "Lenguaje ofensivo hacia el docente")
    assert reporte.estado == "pendiente" and reporte.origen == "usuario"

    reportes.existe.return_value = True
    with pytest.raises(ReporteDuplicado):
        service.reportar(OTRO, 5, "ofensivo", "Lenguaje ofensivo hacia el docente")

    with pytest.raises(SinPermiso):
        service.listar(ESTUDIANTE)


def test_resolver_ocultar_y_publicar():
    reportes = Mock(spec=ReporteRepository)
    evaluaciones = Mock(spec=EvaluacionRepository)
    pendiente = Reporte(id_reporte=1, id_evaluacion=5, id_usuario=2, categoria="spam",
                        motivo="Es publicidad de resúmenes")
    reportes.obtener.return_value = pendiente
    reportes.pendientes_de.return_value = [pendiente]
    evaluaciones.obtener.return_value = Evaluacion(id_evaluacion=5, id_usuario=1, puntaje=1)
    service = ReporteService(reportes, evaluaciones)

    with pytest.raises(SinPermiso):
        service.resolver(ESTUDIANTE, 1, "ocultar")
    with pytest.raises(DatoInvalido):
        service.resolver(ADMIN, 1, "borrar")

    service.resolver(ADMIN, 1, "ocultar")
    assert evaluaciones.guardar.call_args.args[0].estado == "oculta"
    assert pendiente.estado == "revisado"
    assert pendiente.resuelto_por == ADMIN.id_usuario
    assert pendiente.fecha_resolucion is not None
    evaluaciones.eliminar.assert_not_called()

    pendiente.estado = "pendiente"
    service.resolver(ADMIN, 1, "publicar")
    assert evaluaciones.guardar.call_args.args[0].estado == "publicada"
    assert pendiente.estado == "descartado"


class HasherFalso(Hasher):
    def hashear(self, texto):
        return "hash-" + texto

    def verificar(self, texto, hash_guardado):
        return hash_guardado == "hash-" + texto


@pytest.fixture
def cuenta():
    repo = Mock(spec=UsuarioRepository)
    repo.por_correo.return_value = None
    repo.ultimo_codigo.return_value = None
    repo.contar_codigos_desde.return_value = 0
    repo.guardar.side_effect = lambda u: Usuario(u.correo_institucional, u.rol, id_usuario=1)
    tokens = Mock(spec=GestorTokens)
    tokens.crear.return_value = "token-jwt"
    correo = Mock(spec=EnviadorCorreo)
    service = CuentaService(repo, HasherFalso(), tokens, correo, ["academia.umb.edu.co"], 10,
                            generador=lambda: "123456", reloj=lambda: AHORA)
    return service, repo, tokens, correo


def test_solicitar_codigo_registra_usuario_nuevo_y_envia_correo(cuenta):
    service, repo, _, correo = cuenta
    assert service.solicitar_codigo("Ana@academia.umb.edu.co") == "123456"
    repo.guardar.assert_called_once()
    guardado = repo.guardar_codigo.call_args.args[0]
    assert guardado.codigo_hash == "hash-123456"
    assert guardado.expira == AHORA + timedelta(minutes=10)
    correo.enviar_codigo.assert_called_once_with("ana@academia.umb.edu.co", "123456")


def test_no_se_puede_pedir_otro_codigo_antes_de_un_minuto(cuenta):
    service, repo, _, correo = cuenta
    repo.por_correo.return_value = Usuario("ana@academia.umb.edu.co", id_usuario=1)
    repo.ultimo_codigo.return_value = CodigoOtp(1, "hash", AHORA + timedelta(minutes=9),
                                                creado=AHORA - timedelta(seconds=20))
    with pytest.raises(DemasiadosIntentos, match="Espera 41 segundos"):
        service.solicitar_codigo("ana@academia.umb.edu.co")
    correo.enviar_codigo.assert_not_called()

    repo.ultimo_codigo.return_value.creado = AHORA - timedelta(seconds=61)
    assert service.solicitar_codigo("ana@academia.umb.edu.co") == "123456"


def test_maximo_cinco_codigos_por_hora(cuenta):
    service, repo, _, _ = cuenta
    repo.por_correo.return_value = Usuario("ana@academia.umb.edu.co", id_usuario=1)
    repo.contar_codigos_desde.return_value = 5
    with pytest.raises(DemasiadosIntentos, match="una hora"):
        service.solicitar_codigo("ana@academia.umb.edu.co")
    assert repo.contar_codigos_desde.call_args.args[1] == AHORA - timedelta(hours=1)


def test_verificar_codigo_correcto_entrega_token_sin_correo(cuenta):
    service, repo, tokens, _ = cuenta
    repo.por_correo.return_value = Usuario("ana@academia.umb.edu.co", id_usuario=1)
    repo.ultimo_codigo.return_value = CodigoOtp(1, "hash-123456", AHORA + timedelta(minutes=5))

    assert service.verificar_codigo("ana@academia.umb.edu.co", "123456") == "token-jwt"
    sesion = tokens.crear.call_args.args[0]
    assert sesion == Sesion(id_usuario=1, rol="estudiante")
    assert repo.guardar_codigo.call_args.args[0].usado


def test_verificar_codigo_incorrecto_suma_intento(cuenta):
    service, repo, _, _ = cuenta
    repo.por_correo.return_value = Usuario("ana@academia.umb.edu.co", id_usuario=1)
    repo.ultimo_codigo.return_value = CodigoOtp(1, "hash-123456", AHORA + timedelta(minutes=5))
    with pytest.raises(CodigoInvalido):
        service.verificar_codigo("ana@academia.umb.edu.co", "000000")
    assert repo.guardar_codigo.call_args.args[0].intentos == 1


def test_verificar_codigo_vencido_o_bloqueado(cuenta):
    service, repo, _, _ = cuenta
    repo.por_correo.return_value = Usuario("ana@academia.umb.edu.co", id_usuario=1)
    repo.ultimo_codigo.return_value = CodigoOtp(1, "hash-123456", AHORA - timedelta(minutes=1))
    with pytest.raises(CodigoInvalido):
        service.verificar_codigo("ana@academia.umb.edu.co", "123456")

    repo.ultimo_codigo.return_value = CodigoOtp(1, "hash-123456", AHORA + timedelta(minutes=5),
                                                intentos=5)
    with pytest.raises(DemasiadosIntentos):
        service.verificar_codigo("ana@academia.umb.edu.co", "123456")


def test_verificar_sin_haber_pedido_codigo(cuenta):
    service, *_ = cuenta
    with pytest.raises(CodigoInvalido):
        service.verificar_codigo("nuevo@academia.umb.edu.co", "123456")
