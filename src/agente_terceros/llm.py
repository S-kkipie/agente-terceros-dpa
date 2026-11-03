"""Proveedores de IA intercambiables: OpenRouter (por defecto, con Gemini), Gemini directo,
OpenAI u OpenAI-compatible, Anthropic y Ollama local.

Todos se exponen con la misma firma LLM = (prompt: str) -> str. Se elige con
TERCEROS_LLM_PROVIDER y, opcionalmente, TERCEROS_LLM_MODEL y TERCEROS_LLM_BASE_URL
(OpenRouter, Groq, DeepSeek, LM Studio o cualquier servidor compatible con OpenAI).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Callable

import requests

from .config import Config

LLM = Callable[[str], str]

NOMBRES = {
    "openrouter": "OpenRouter",
    "gemini": "Gemini",
    "openai": "OpenAI / compatible",
    "anthropic": "Anthropic",
    "ollama": "Ollama (local)",
}
MODELOS = {
    "openrouter": "google/gemini-2.5-flash",
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-5",
    "ollama": "qwen3:4b",
}
CLAVES = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "gemini": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "ollama": (),
}
TIMEOUT = 300


class RegistroGasto:
    """Gasto acumulado en IA (USD y tokens), persistido en un JSON."""

    def __init__(self, ruta: Path):
        self.ruta = ruta

    def _leer(self) -> dict:
        try:
            return json.loads(self.ruta.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {"usd": 0.0, "llamadas": 0, "tokens_entrada": 0, "tokens_salida": 0}

    def sumar(self, usd: float, tokens_entrada: int, tokens_salida: int) -> None:
        d = self._leer()
        d["usd"] += usd or 0.0
        d["llamadas"] += 1
        d["tokens_entrada"] += tokens_entrada or 0
        d["tokens_salida"] += tokens_salida or 0
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(json.dumps(d), encoding="utf-8")

    def resumen(self) -> dict:
        d = self._leer()
        return {**d, "usd": round(d["usd"], 6)}


def con_cache(
    llm: LLM, directorio: Path, etiqueta: str, valida: Callable[[str], bool] | None = None
) -> LLM:
    """Reutiliza la respuesta de un prompt idéntico (mismo contrato, misma pregunta, mismo
    modelo): repetir una demostración no vuelve a costar. Solo guarda respuestas válidas,
    para que un reintento no reciba la misma respuesta defectuosa."""

    def llamar(prompt: str) -> str:
        clave = hashlib.sha256(f"{etiqueta}\0{prompt}".encode()).hexdigest()
        ruta = directorio / f"{clave}.txt"
        if ruta.exists():
            return ruta.read_text(encoding="utf-8")
        respuesta = llm(prompt)
        if valida is None or valida(respuesta):
            directorio.mkdir(parents=True, exist_ok=True)
            ruta.write_text(respuesta, encoding="utf-8")
        return respuesta

    return llamar


def etiqueta(cfg: Config) -> str:
    return f"{cfg.llm_provider}/{modelo(cfg)}"


def modelo(cfg: Config) -> str:
    return cfg.llm_model or MODELOS.get(cfg.llm_provider, "")


def descripcion(cfg: Config) -> str:
    return f"{NOMBRES.get(cfg.llm_provider, cfg.llm_provider)} · {modelo(cfg)}"


def _clave(proveedor: str) -> str:
    variables = CLAVES[proveedor]
    for v in variables:
        if os.getenv(v):
            return os.environ[v]
    raise RuntimeError(f"Falta {' o '.join(variables)} en .env para usar el proveedor {proveedor}")


def _sin_razonamiento(texto: str) -> str:
    # Modelos con razonamiento visible (qwen3, deepseek-r1) lo envuelven en <think>.
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.S).strip()


def _gemini(cfg: Config, json_salida: bool, gasto: RegistroGasto | None = None) -> LLM:
    import logging

    from google import genai
    from google.genai import types

    # Aviso ruidoso e irrelevante del SDK sobre "automatic function calling".
    logging.getLogger("google_genai.models").setLevel(logging.ERROR)
    # Un solo intento con timeout: sin esto el SDK reintenta largo rato ante cuotas agotadas.
    cliente = genai.Client(
        api_key=_clave("gemini"),
        http_options=types.HttpOptions(
            timeout=120_000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )

    def llamar(prompt: str) -> str:
        r = cliente.models.generate_content(
            model=modelo(cfg),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=cfg.temperature,
                response_mime_type="application/json" if json_salida else "text/plain",
            ),
        )
        return r.text

    return llamar


def _openai(cfg: Config, json_salida: bool, gasto: RegistroGasto | None = None) -> LLM:
    clave = _clave("openai")
    base = (cfg.llm_base_url or "https://api.openai.com/v1").rstrip("/")

    def llamar(prompt: str) -> str:
        cuerpo = {
            "model": modelo(cfg),
            "temperature": cfg.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if json_salida:
            cuerpo["response_format"] = {"type": "json_object"}
        r = requests.post(
            f"{base}/chat/completions", json=cuerpo,
            headers={"Authorization": f"Bearer {clave}"}, timeout=TIMEOUT,
        )
        r.raise_for_status()
        return _sin_razonamiento(r.json()["choices"][0]["message"]["content"])

    return llamar


def _openrouter(cfg: Config, json_salida: bool, gasto: RegistroGasto | None = None) -> LLM:
    clave = _clave("openrouter")
    base = (cfg.llm_base_url or "https://openrouter.ai/api/v1").rstrip("/")

    def llamar(prompt: str) -> str:
        cuerpo = {
            "model": modelo(cfg),
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "reasoning": {"enabled": False},  # sin tokens de razonamiento: más barato y rápido
            "usage": {"include": True},  # OpenRouter devuelve el costo de cada llamada
        }
        if json_salida:
            cuerpo["response_format"] = {"type": "json_object"}
        r = requests.post(
            f"{base}/chat/completions", json=cuerpo, timeout=TIMEOUT,
            headers={
                "Authorization": f"Bearer {clave}",
                "HTTP-Referer": "https://github.com/S-kkipie/agente-terceros-dpa",
                "X-Title": "Agente de Terceros (DPAs)",
            },
        )
        if r.status_code == 402:
            raise RuntimeError("OpenRouter sin saldo: la cuenta no tiene créditos "
                               "(recárgalos en openrouter.ai/settings/credits)")
        if r.status_code == 429:
            raise RuntimeError("OpenRouter rechazó la solicitud por límite de uso (429)")
        r.raise_for_status()
        datos = r.json()
        if "error" in datos:
            raise RuntimeError(datos["error"].get("message", str(datos["error"])))
        uso = datos.get("usage") or {}
        if gasto is not None:
            gasto.sumar(uso.get("cost", 0.0), uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0))
        return _sin_razonamiento(datos["choices"][0]["message"]["content"])

    return llamar


def _anthropic(cfg: Config, json_salida: bool, gasto: RegistroGasto | None = None) -> LLM:
    clave = _clave("anthropic")
    base = (cfg.llm_base_url or "https://api.anthropic.com").rstrip("/")

    def llamar(prompt: str) -> str:
        # Sin modo JSON nativo: el prompt ya exige JSON y parsear_json tolera texto extra.
        r = requests.post(
            f"{base}/v1/messages",
            json={
                "model": modelo(cfg),
                "max_tokens": 8192,
                "temperature": cfg.temperature,
                "messages": [{"role": "user", "content": prompt}],
            },
            headers={"x-api-key": clave, "anthropic-version": "2023-06-01"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return "".join(b["text"] for b in r.json()["content"] if b.get("type") == "text")

    return llamar


def _ollama(cfg: Config, json_salida: bool, gasto: RegistroGasto | None = None) -> LLM:
    base = (cfg.llm_base_url or cfg.ollama_url).rstrip("/")

    def llamar(prompt: str) -> str:
        cuerpo = {
            "model": modelo(cfg),
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": cfg.temperature, "num_ctx": 16384},
        }
        if json_salida:
            cuerpo["format"] = "json"
        r = requests.post(f"{base}/api/chat", json=cuerpo, timeout=TIMEOUT)
        r.raise_for_status()
        return _sin_razonamiento(r.json()["message"]["content"])

    return llamar


FABRICAS = {
    "openrouter": _openrouter, "gemini": _gemini, "openai": _openai,
    "anthropic": _anthropic, "ollama": _ollama,
}


def crear_llm(cfg: Config, json_salida: bool = True, gasto: RegistroGasto | None = None) -> LLM:
    """LLM del proveedor configurado. json_salida pide respuesta JSON si el proveedor lo admite;
    gasto acumula el costo informado por el proveedor (OpenRouter)."""
    if cfg.llm_provider not in FABRICAS:
        raise ValueError(
            f"Proveedor de IA desconocido: {cfg.llm_provider!r}. Opciones: {', '.join(FABRICAS)}"
        )
    return FABRICAS[cfg.llm_provider](cfg, json_salida, gasto)


def crear_llm_con_respaldo(
    cfg: Config, json_salida: bool = True, gasto: RegistroGasto | None = None,
    estado: dict | None = None,
) -> LLM:
    """Prueba el proveedor principal y, si falla, los de cfg.llm_respaldo en orden.
    `estado` registra qué proveedor respondió y los errores de los que fallaron."""
    from dataclasses import replace

    estado = estado if estado is not None else {}
    nombres = [cfg.llm_provider] + [p for p in cfg.llm_respaldo if p != cfg.llm_provider]

    def llamar(prompt: str) -> str:
        errores = []
        for nombre in nombres:
            sub = cfg if nombre == cfg.llm_provider else replace(cfg, llm_provider=nombre, llm_model="", llm_base_url="")
            try:
                respuesta = FABRICAS[nombre](sub, json_salida, gasto)(prompt)
            except Exception as e:  # noqa: BLE001 — cualquier falla del proveedor activa el respaldo
                errores.append(f"{nombre}: {e}")
                continue
            estado.update(ultimo=nombre, modelo=descripcion(sub), errores=errores)
            return respuesta
        estado.update(ultimo=None, errores=errores)
        raise RuntimeError("Ningún proveedor de IA respondió. " + " | ".join(errores))

    return llamar
