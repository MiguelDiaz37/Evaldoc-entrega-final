import httpx
from google import genai
from google.genai import errors, types

from app.domain.ia.ports import ModeloIA, RespuestaModelo
from app.domain.exceptions import IAError, IALimiteAlcanzado, IANoConfigurada, IATiempoAgotado


class GeminiClient(ModeloIA):
    def __init__(self, api_key, modelo, timeout_ms=20000, respuesta_json=False,
                 sin_razonamiento=False):
        self.api_key = api_key
        self.modelo = modelo
        self.timeout_ms = timeout_ms
        self.respuesta_json = respuesta_json
        self.sin_razonamiento = sin_razonamiento

    def configuracion(self, con_razonamiento_minimo=True):
        opciones = {}
        if self.respuesta_json:
            opciones["response_mime_type"] = "application/json"
        if self.sin_razonamiento and con_razonamiento_minimo:
            if self.modelo.startswith("gemini-2"):
                opciones["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
            else:
                opciones["thinking_config"] = types.ThinkingConfig(thinking_level="minimal")
        return types.GenerateContentConfig(**opciones) if opciones else None

    def llamar(self, client, prompt):
        try:
            return client.models.generate_content(model=self.modelo, contents=prompt,
                                                  config=self.configuracion())
        except errors.APIError as e:
            if e.code == 400 and "thinking" in str(e.message).lower():
                return client.models.generate_content(model=self.modelo, contents=prompt,
                                                      config=self.configuracion(False))
            raise

    def generar(self, prompt):
        if not self.api_key:
            raise IANoConfigurada("GEMINI_API_KEY is not configured")

        client = genai.Client(api_key=self.api_key,
                              http_options=types.HttpOptions(timeout=self.timeout_ms))
        try:
            res = self.llamar(client, prompt)
        except httpx.TimeoutException:
            raise IATiempoAgotado("Gemini took too long to answer")
        except errors.APIError as e:
            if e.code == 429:
                raise IALimiteAlcanzado("Rate limit reached, try again later")
            raise IAError("Error from Gemini: " + str(e.message))

        entrada = 0
        salida = 0
        if res.usage_metadata:
            entrada = res.usage_metadata.prompt_token_count or 0
            salida = (res.usage_metadata.candidates_token_count or 0) + (
                res.usage_metadata.thoughts_token_count or 0
            )
        return RespuestaModelo(texto=res.text or "", tokens_entrada=entrada, tokens_salida=salida)
