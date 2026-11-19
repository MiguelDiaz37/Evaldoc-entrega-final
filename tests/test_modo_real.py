from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from app import config
from app.application.cuenta_service import CuentaService
from app.domain.cuentas.entities import CodigoOtp, Usuario
from app.domain.cuentas.ports import EnviadorCorreo, GestorTokens, Hasher, UsuarioRepository
from app.domain.exceptions import CorreoNoEnviado
from app.infrastructure.seguridad.adaptadores import CorreoSmtp


def test_si_el_correo_falla_se_borra_el_codigo():
    repo = Mock(spec=UsuarioRepository)
    repo.por_correo.return_value = Usuario("ana@academia.umb.edu.co", id_usuario=1)
    repo.ultimo_codigo.return_value = None
    repo.contar_codigos_desde.return_value = 0
    repo.guardar_codigo.side_effect = lambda c: CodigoOtp(c.id_usuario, c.codigo_hash, c.expira, id_codigo=7)
    correo = Mock(spec=EnviadorCorreo)
    correo.enviar_codigo.side_effect = OSError("sin conexion")
    hasher = Mock(spec=Hasher)
    hasher.hashear.return_value = "hash"
    service = CuentaService(repo, hasher, Mock(spec=GestorTokens), correo, ["academia.umb.edu.co"],
                            reloj=lambda: datetime(2026, 11, 16))

    with pytest.raises(CorreoNoEnviado):
        service.solicitar_codigo("ana@academia.umb.edu.co")
    repo.eliminar_codigo.assert_called_once_with(7)


def test_mensaje_de_correo_trae_el_codigo_en_texto_y_html():
    mensaje = CorreoSmtp("smtp.x", 587, "u", "p", "evaldoc@x.com", 10).armar_mensaje("ana@academia.umb.edu.co", "482913")
    assert "482913" in mensaje["Subject"]
    assert mensaje["From"].startswith("EvalDoc <") and "UMB" not in mensaje["From"]
    tipos = {p.get_content_type(): p.get_content() for p in mensaje.iter_parts()}
    assert "482913" in tipos["text/plain"] and "482913" in tipos["text/html"]
    assert "10 minutos" in tipos["text/plain"]


@pytest.mark.parametrize("puerto, clase, usa_starttls", [(587, "SMTP", True), (465, "SMTP_SSL", False)])
def test_correo_usa_tls_segun_el_puerto(puerto, clase, usa_starttls):
    conexion = MagicMock()
    with patch(f"smtplib.{clase}") as smtp:
        smtp.return_value.__enter__.return_value = conexion
        CorreoSmtp("smtp.gmail.com", puerto, "u@gmail.com", "clave", "u@gmail.com").enviar_codigo("a@b.co", "111111")
    smtp.assert_called_once()
    assert conexion.starttls.called == usa_starttls
    conexion.login.assert_called_once_with("u@gmail.com", "clave")
    conexion.send_message.assert_called_once()


def test_modo_real_exige_clave_jwt_propia_y_correo(monkeypatch):
    monkeypatch.setattr(config, "MODO_DEMO", False)
    monkeypatch.setattr(config, "JWT_SECRETO", config.CLAVE_DESARROLLO)
    monkeypatch.setattr(config, "SMTP_SERVIDOR", "")
    errores, _ = config.problemas_de_configuracion()
    assert any("JWT_SECRETO" in e for e in errores)
    assert any("SMTP" in e for e in errores)

    monkeypatch.setattr(config, "JWT_SECRETO", "x" * 48)
    monkeypatch.setattr(config, "SMTP_SERVIDOR", "smtp.gmail.com")
    monkeypatch.setattr(config, "SMTP_USUARIO", "u@gmail.com")
    monkeypatch.setattr(config, "SMTP_CLAVE", "clave")
    errores, _ = config.problemas_de_configuracion()
    assert errores == []


def test_modo_demo_no_bloquea_pero_avisa(monkeypatch):
    monkeypatch.setattr(config, "MODO_DEMO", True)
    monkeypatch.setattr(config, "SMTP_SERVIDOR", "")
    errores, avisos = config.problemas_de_configuracion()
    assert errores == []
    assert any("MODO_DEMO" in a for a in avisos)


def test_web_muestra_error_si_el_correo_no_sale(client, datos):
    from app.container import get_enviador_correo
    from app.main import app
    roto = Mock(spec=EnviadorCorreo)
    roto.enviar_codigo.side_effect = OSError("smtp caido")
    app.dependency_overrides[get_enviador_correo] = lambda: roto
    res = client.post("/login", data={"correo": "ana@academia.umb.edu.co", "siguiente": "/"})
    assert res.status_code == 503
    assert "No pudimos enviar el correo" in res.text
    app.dependency_overrides[get_enviador_correo] = lambda: Mock(spec=EnviadorCorreo)
    assert client.post("/login", data={"correo": "ana@academia.umb.edu.co", "siguiente": "/"}).status_code == 200


def test_textos_de_ejemplo_del_env_cuentan_como_vacios(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "pon_aqui_tu_api_key")
    assert config.valor_real("GEMINI_API_KEY") == ""
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaClaveReal")
    assert config.valor_real("GEMINI_API_KEY") == "AIzaClaveReal"


@pytest.mark.parametrize("modelo, budget, nivel", [
    ("gemini-2.5-flash-lite", 0, None),
    ("gemini-3.5-flash-lite", None, "MINIMAL"),
])
def test_gemini_usa_thinking_segun_la_version(modelo, budget, nivel):
    from app.infrastructure.ia.gemini_client import GeminiClient
    pensamiento = GeminiClient("k", modelo, respuesta_json=True, sin_razonamiento=True).configuracion().thinking_config
    assert pensamiento.thinking_budget == budget
    assert (pensamiento.thinking_level.value if pensamiento.thinking_level else None) == nivel


def test_gemini_elige_la_categoria_del_reporte():
    from app.application.moderacion_service import ModeradorIA
    r = ModeradorIA.leer_respuesta('{"veredicto": "bloqueado", "categoria": "datos_personales", "motivo": "telefono"}')
    assert r.categoria == "datos_personales"
    assert ModeradorIA.leer_respuesta('{"veredicto": "bloqueado", "motivo": "x"}').categoria == "ofensivo"
    assert ModeradorIA.leer_respuesta('{"veredicto": "dudoso", "categoria": "rara"}').categoria == "otro"


def test_lista_de_palabras_reporta_como_ofensivo():
    from app.application.moderacion_service import ModeradorPalabras
    assert ModeradorPalabras(["idiota"]).revisar("es un idiota").categoria == "ofensivo"
