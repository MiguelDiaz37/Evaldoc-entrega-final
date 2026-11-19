import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.application.moderacion_service import ModeracionService, ModeradorPalabras
from app.container import get_moderador
from app.infrastructure.db.database import Base, get_db
from app.main import app
from scripts.cargar_datos import cargar

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@event.listens_for(engine, "connect")
def activar_llaves_foraneas(conexion, _):
    # SQLite no revisa las llaves foraneas si no se activan
    conexion.execute("PRAGMA foreign_keys=ON")


TestSession = sessionmaker(bind=engine)


def get_test_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def limpiar_db(monkeypatch):
    monkeypatch.setattr(config, "MODO_DEMO", True)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


moderador_de_prueba = ModeracionService(ModeradorPalabras(["idiota", "imbecil"]))


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_moderador] = lambda: moderador_de_prueba
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def datos():
    db = TestSession()
    cargar(db)
    db.close()


def iniciar_sesion(client, correo):
    res = client.post("/api/v1/auth/otp/solicitar", json={"correo_institucional": correo})
    assert res.status_code == 200, res.text
    codigo = res.json()["codigo_demo"]
    res = client.post("/api/v1/auth/otp/verificar",
                      json={"correo_institucional": correo, "codigo": codigo})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def estudiante(client, datos):
    return iniciar_sesion(client, "ana.perez@academia.umb.edu.co")


@pytest.fixture
def otro_estudiante(client, datos):
    return iniciar_sesion(client, "luis.gomez@academia.umb.edu.co")


@pytest.fixture
def admin(client, datos):
    return iniciar_sesion(client, config.ADMIN_CORREO)
