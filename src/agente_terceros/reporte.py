"""Salidas para la línea de comandos: informe Markdown de una revisión y diagnóstico
del entorno (lo que hay que comprobar antes de una demostración)."""

from __future__ import annotations

import requests

from .config import Config
from .llm import CLAVES, descripcion, _clave

ORDEN = {"falta": 0, "parcial": 1, "cumple": 2}
ICONO = {"falta": "✗ Falta", "parcial": "◐ Parcial", "cumple": "✓ Cumple"}


def informe_markdown(revision: dict, archivo: str) -> str:
    res = sorted(revision["resultados"], key=lambda r: (ORDEN[r["estado"]], -r["peso"]))
    cuenta = {e: sum(r["estado"] == e for r in res) for e in ORDEN}
    lineas = [
        f"# Revisión del contrato de encargo: {archivo}",
        "",
        f"**Cumplimiento ponderado: {revision['cumplimiento']:.1f} %** "
        f"({cuenta['cumple']} cumplen · {cuenta['parcial']} parciales · {cuenta['falta']} faltan)",
        "",
        revision.get("resumen", ""),
        "",
        "> Resultado generado por el Agente de Terceros. Queda pendiente de aprobación de "
        "Asesoría Legal / DPO antes de surtir efecto.",
        "",
    ]
    fuentes = revision.get("fuentes", {})
    for r in res:
        lineas += [
            f"## {ICONO[r['estado']]} — {r['titulo']}",
            f"*RGPD {r['rgpd']} · {r['peru']} · ISO/IEC 27701 {', '.join(r['iso'])} · peso {r['peso']}*",
            "",
        ]
        if r["evidencia"]:
            aviso = "" if r["evidencia_verificada"] else " *(cita no verificada: revisar manualmente)*"
            lineas += [f"> {r['evidencia']}{aviso}", ""]
        if r["recomendacion"]:
            lineas += [f"**Recomendación:** {r['recomendacion']}", ""]
        refs = [fuentes[str(n)]["etiqueta"] for n in r["fundamento"] if str(n) in fuentes]
        if refs:
            lineas += [f"Fundamento: {' · '.join(refs)}", ""]
    return "\n".join(lineas).rstrip() + "\n"


def diagnosticar(cfg: Config) -> list[tuple[str, bool, str]]:
    """Comprobaciones previas a usar el agente: (nombre, ok, detalle)."""
    res: list[tuple[str, bool, str]] = []
    try:
        modelos = [m["name"] for m in requests.get(f"{cfg.ollama_url}/api/tags", timeout=5).json()["models"]]
        res.append(("Ollama en ejecución", True, cfg.ollama_url))
        presente = any(m.split(":")[0] == cfg.embedding_model.split(":")[0] for m in modelos)
        res.append(("Modelo de embeddings", presente,
                    cfg.embedding_model if presente else f"ejecuta: ollama pull {cfg.embedding_model}"))
    except requests.RequestException:
        res.append(("Ollama en ejecución", False, f"no responde en {cfg.ollama_url}: ejecuta ollama serve"))
        res.append(("Modelo de embeddings", False, "requiere Ollama"))

    indice = cfg.index_dir / "normativa.faiss"
    res.append(("Índice FAISS", indice.exists(),
                 str(indice) if indice.exists() else "ejecuta: agente-terceros ingest"))

    try:
        if CLAVES.get(cfg.llm_provider):
            _clave(cfg.llm_provider)
        res.append(("Clave del proveedor de IA", True, descripcion(cfg)))
    except (RuntimeError, KeyError) as e:
        res.append(("Clave del proveedor de IA", False, str(e)))
        return res

    if cfg.llm_provider == "openrouter":
        try:
            d = requests.get(
                "https://openrouter.ai/api/v1/key", timeout=10,
                headers={"Authorization": f"Bearer {_clave('openrouter')}"},
            ).json()["data"]
            restante, limite = d.get("limit_remaining"), d.get("limit")
            if restante is None:
                res.append(("Saldo de OpenRouter", True, f"sin límite · usado US$ {d.get('usage', 0):.2f}"))
            else:
                res.append(("Saldo de OpenRouter", restante > 0.05,
                            f"US$ {restante:.2f} de {limite:.2f} disponibles"))
        except (requests.RequestException, KeyError, ValueError) as e:
            res.append(("Saldo de OpenRouter", False, f"no se pudo consultar: {e}"))
    return res
