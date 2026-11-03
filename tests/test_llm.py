from dataclasses import replace

import pytest

from agente_terceros import llm
from agente_terceros.config import get_config


class Respuesta:
    status_code = 200

    def __init__(self, datos: dict):
        self.datos = datos

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self.datos


@pytest.fixture
def capturar(monkeypatch):
    """Sustituye requests.post y devuelve lo que se envió."""
    enviado: dict = {}

    def instalar(respuesta: dict):
        def post(url, json=None, headers=None, timeout=None):
            enviado.update(url=url, json=json, headers=headers or {})
            return Respuesta(respuesta)

        monkeypatch.setattr(llm.requests, "post", post)
        return enviado

    return instalar


def _cfg(proveedor: str, **extra):
    return replace(get_config(), llm_provider=proveedor, llm_model="", llm_base_url="", **extra)


def test_openai_usa_chat_completions_con_modo_json(capturar, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    enviado = capturar({"choices": [{"message": {"content": '{"ok": 1}'}}]})
    salida = llm.crear_llm(_cfg("openai"))("hola")
    assert salida == '{"ok": 1}'
    assert enviado["url"] == "https://api.openai.com/v1/chat/completions"
    assert enviado["headers"]["Authorization"] == "Bearer sk-test"
    assert enviado["json"]["response_format"] == {"type": "json_object"}
    assert enviado["json"]["messages"][-1] == {"role": "user", "content": "hola"}


def test_openai_compatible_respeta_base_url_y_modelo(capturar, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    enviado = capturar({"choices": [{"message": {"content": "texto"}}]})
    cfg = replace(_cfg("openai"), llm_base_url="https://openrouter.ai/api/v1/", llm_model="deepseek/deepseek-chat")
    llm.crear_llm(cfg, json_salida=False)("hola")
    assert enviado["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert enviado["json"]["model"] == "deepseek/deepseek-chat"
    assert "response_format" not in enviado["json"]


def test_anthropic_usa_messages_y_une_bloques_de_texto(capturar, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak")
    enviado = capturar({"content": [{"type": "text", "text": '{"a":'}, {"type": "text", "text": " 1}"}]})
    salida = llm.crear_llm(_cfg("anthropic"))("hola")
    assert salida == '{"a": 1}'
    assert enviado["url"] == "https://api.anthropic.com/v1/messages"
    assert enviado["headers"]["x-api-key"] == "ak"
    assert "anthropic-version" in enviado["headers"]
    assert enviado["json"]["max_tokens"] > 0


def test_ollama_local_pide_json_y_quita_razonamiento(capturar):
    enviado = capturar({"message": {"content": "<think>pensando…</think>\n{\"a\": 1}"}})
    cfg = _cfg("ollama")
    salida = llm.crear_llm(cfg)("hola")
    assert salida == '{"a": 1}'
    assert enviado["url"] == f"{cfg.ollama_url}/api/chat"
    assert enviado["json"]["format"] == "json" and enviado["json"]["stream"] is False


def test_proveedor_desconocido_lista_las_opciones():
    with pytest.raises(ValueError, match="gemini"):
        llm.crear_llm(_cfg("watson"))


def test_falta_clave_indica_la_variable_de_entorno(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        llm.crear_llm(_cfg("anthropic"))


def test_descripcion_usa_el_modelo_configurado():
    cfg = replace(_cfg("ollama"), llm_model="llama3.1:8b")
    assert llm.descripcion(cfg) == "Ollama (local) · llama3.1:8b"


def test_openrouter_es_el_proveedor_por_defecto_con_gemini():
    from agente_terceros.config import Config

    assert Config.__dataclass_fields__["llm_provider"].default in ("openrouter", Config().llm_provider)
    cfg = _cfg("openrouter")
    assert llm.descripcion(cfg) == "OpenRouter · google/gemini-2.5-flash"


def test_openrouter_desactiva_razonamiento_limita_salida_y_registra_costo(capturar, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-x")
    enviado = capturar({
        "choices": [{"message": {"content": '{"ok": 1}'}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "cost": 0.0008},
    })
    gasto = llm.RegistroGasto(tmp_path / "gasto.json")
    salida = llm.crear_llm(_cfg("openrouter"), gasto=gasto)("hola")
    assert salida == '{"ok": 1}'
    assert enviado["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert enviado["headers"]["Authorization"] == "Bearer sk-or-x"
    assert enviado["json"]["model"] == "google/gemini-2.5-flash"
    assert enviado["json"]["reasoning"] == {"enabled": False}
    assert enviado["json"]["usage"] == {"include": True}
    assert 0 < enviado["json"]["max_tokens"] <= 10000
    assert gasto.resumen() == {"usd": 0.0008, "llamadas": 1, "tokens_entrada": 1000, "tokens_salida": 200}


def test_registro_de_gasto_acumula_y_persiste(tmp_path):
    ruta = tmp_path / "g.json"
    llm.RegistroGasto(ruta).sumar(0.01, 10, 5)
    otro = llm.RegistroGasto(ruta)
    otro.sumar(0.02, 20, 5)
    assert otro.resumen() == {"usd": 0.03, "llamadas": 2, "tokens_entrada": 30, "tokens_salida": 10}


def test_cache_evita_pagar_dos_veces_el_mismo_prompt(tmp_path):
    llamadas = []

    def base(prompt):
        llamadas.append(prompt)
        return f"resp:{prompt}"

    cacheado = llm.con_cache(base, tmp_path, "openrouter/google/gemini-2.5-flash")
    assert cacheado("a") == "resp:a" and cacheado("a") == "resp:a"
    assert cacheado("b") == "resp:b"
    assert llamadas == ["a", "b"]
    # Persiste en disco: otra instancia tampoco vuelve a llamar.
    assert llm.con_cache(base, tmp_path, "openrouter/google/gemini-2.5-flash")("a") == "resp:a"
    assert llamadas == ["a", "b"]
    # Otro modelo no reutiliza la respuesta.
    llm.con_cache(base, tmp_path, "otro/modelo")("a")
    assert llamadas == ["a", "b", "a"]


def test_cache_no_guarda_respuestas_invalidas(tmp_path):
    respuestas = iter(["{roto", '{"ok": 1}'])
    cacheado = llm.con_cache(lambda p: next(respuestas), tmp_path, "x", valida=lambda r: r.startswith('{"'))
    assert cacheado("a") == "{roto"  # se devuelve, pero no se guarda
    assert cacheado("a") == '{"ok": 1}'
    assert cacheado("a") == '{"ok": 1}'  # esta sí quedó en caché


def test_respaldo_pasa_al_siguiente_proveedor_si_falla(monkeypatch):
    usados = []

    def fabrica(nombre, falla):
        def f(cfg, json_salida, gasto=None):
            def llamar(prompt):
                usados.append(nombre)
                if falla:
                    raise RuntimeError(f"{nombre} caído")
                return f"respuesta de {nombre}"
            return llamar
        return f

    monkeypatch.setattr(llm, "FABRICAS", {"openrouter": fabrica("openrouter", True),
                                          "gemini": fabrica("gemini", False),
                                          "ollama": fabrica("ollama", False)})
    cfg = replace(_cfg("openrouter"), llm_respaldo=("gemini", "ollama"))
    estado = {}
    salida = llm.crear_llm_con_respaldo(cfg, estado=estado)("hola")
    assert salida == "respuesta de gemini" and usados == ["openrouter", "gemini"]
    assert estado["ultimo"] == "gemini" and "openrouter caído" in estado["errores"][0]


def test_respaldo_omite_proveedores_sin_clave_y_falla_si_todos_fallan(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def caido(cfg, json_salida, gasto=None):
        def llamar(prompt):
            raise RuntimeError("sin servicio")
        return llamar

    monkeypatch.setattr(llm, "FABRICAS", {**llm.FABRICAS, "openrouter": caido, "ollama": caido})
    cfg = replace(_cfg("openrouter"), llm_respaldo=("anthropic", "ollama"))
    with pytest.raises(RuntimeError, match="Ningún proveedor de IA respondió"):
        llm.crear_llm_con_respaldo(cfg)("hola")


def test_openrouter_sin_saldo_da_mensaje_claro(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")

    class R402:
        status_code = 402

        def json(self):
            return {"error": {"message": "Insufficient credits"}}

        def raise_for_status(self):
            raise llm.requests.HTTPError("402 Client Error", response=self)

    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: R402())
    with pytest.raises(RuntimeError, match="sin saldo"):
        llm.crear_llm(_cfg("openrouter"))("hola")
