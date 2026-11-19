from fastapi import APIRouter, Depends

from app import config
from app.api.schemas import (
    SesionOut,
    SolicitarCodigoIn,
    SolicitarCodigoOut,
    TokenOut,
    VerificarCodigoIn,
)
from app.application.cuenta_service import CuentaService
from app.container import get_cuenta_service, get_sesion, get_tokens

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


@router.post(
    "/otp/solicitar",
    response_model=SolicitarCodigoOut,
    summary="Pedir código de acceso",
    description="Envía un código de 6 dígitos al correo institucional. Si el correo es "
    "nuevo, registra al usuario en el mismo paso.",
    responses={422: {"description": "Correo no institucional"}},
)
def solicitar_codigo(datos: SolicitarCodigoIn,
                     service: CuentaService = Depends(get_cuenta_service)):
    codigo = service.solicitar_codigo(datos.correo_institucional)
    return SolicitarCodigoOut(
        mensaje="Te enviamos un código de acceso a tu correo institucional",
        codigo_demo=codigo if config.MODO_DEMO else None,
    )


@router.post(
    "/otp/verificar",
    response_model=TokenOut,
    summary="Verificar código y obtener token",
    description="Si el código es correcto devuelve un JWT. El token guarda el id y el rol, "
    "nunca el correo.",
    responses={401: {"description": "Código incorrecto o vencido"},
               429: {"description": "Demasiados intentos"}},
)
def verificar_codigo(datos: VerificarCodigoIn,
                     service: CuentaService = Depends(get_cuenta_service),
                     tokens=Depends(get_tokens)):
    token = service.verificar_codigo(datos.correo_institucional, datos.codigo)
    return TokenOut(access_token=token, rol=tokens.leer(token).rol)


@router.get("/yo", response_model=SesionOut, summary="Ver mi sesión")
def yo(sesion=Depends(get_sesion)):
    return sesion
