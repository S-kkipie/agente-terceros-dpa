"""Orquestación multiagente sobre el bus MCP.

Dos flujos del PIMS en los que otro agente coordina al Agente de Terceros llamando a
sus herramientas MCP (JSON-RPC). La decisión final siempre queda en manos humanas.

- Brecha de seguridad: el Agente de Incidentes pregunta qué encargados tratan los datos
  afectados, revisa su DPA y su riesgo y prepara las acciones para el DPO.
- Renovaciones: el orquestador revisa todos los encargados y genera tareas por DPAs
  ausentes, vencidos, por vencer o pendientes.

Los flujos reciben `llamar(herramienta, argumentos)`, así que funcionan igual con el
servidor en proceso (pruebas) que por stdio (`agente-terceros orquestar ...`).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any, Awaitable, Callable

Llamar = Callable[[str, dict], Awaitable[Any]]
Log = Callable[[dict], None]

PRIORIDAD = {"alta": 0, "media": 1, "baja": 2}


def _recortar(texto: str, n: int = 200) -> str:
    """Recorta en el último espacio antes de n caracteres, sin partir palabras."""
    if len(texto) <= n:
        return texto
    return texto[:n].rsplit(" ", 1)[0] + "…"


async def _paso(llamar: Llamar, log: Log | None, pasos: list, agente: str, herramienta: str,
                argumentos: dict, resumir: Callable[[Any], str]) -> Any:
    resultado = await llamar(herramienta, argumentos)
    paso = {"agente": agente, "herramienta": herramienta, "argumentos": argumentos,
            "resultado": resumir(resultado)}
    pasos.append(paso)
    if log:
        log(paso)
    return resultado


async def flujo_brecha(llamar: Llamar, categoria: str, descripcion: str = "",
                       log: Log | None = None) -> dict:
    pasos: list[dict] = []
    incidentes = "Agente de Incidentes"
    implicados = await _paso(
        llamar, log, pasos, incidentes, "processors_in_breach", {"termino": categoria},
        lambda r: f"{len(r)} encargado(s): {', '.join(p['nombre'] for p in r) or 'ninguno'}",
    )
    acciones = []
    for p in implicados:
        estado = await _paso(
            llamar, log, pasos, incidentes, "check_dpa_status", {"proveedor_id": p["id"]},
            lambda r, n=p["nombre"]: f"{n}: DPA {r['estado']}",
        )
        riesgo = await _paso(
            llamar, log, pasos, incidentes, "evaluate_vendor", {"proveedor_id": p["id"]},
            lambda r, n=p["nombre"]: f"{n}: riesgo {r['nivel']} ({r['puntaje']}/16)",
        )
        clausula_falla = p["clausula_notificacion"] != "cumple"
        dpa_no_vigente = estado["estado"] not in ("vigente", "por_vencer")
        sin_garantia = clausula_falla or dpa_no_vigente
        alta = sin_garantia or riesgo["nivel"] in ("alto", "crítico")
        if clausula_falla:
            accion = ("Contactar de inmediato al encargado y exigir su informe del incidente: el "
                      "contrato no garantiza la notificación (RLPDP art. 36).")
        elif dpa_no_vigente:
            accion = ("Contactar de inmediato al encargado y exigir su informe del incidente: el "
                      "contrato incluye la cláusula de notificación, pero el DPA no está vigente "
                      f"({estado['estado'].replace('_', ' ')}).")
        else:
            accion = ("Solicitar el informe del incidente en el plazo pactado en el DPA: "
                      f"«{_recortar(p['evidencia'])}».")
        acciones.append({
            "proveedor": p["nombre"], "contacto": p["contacto"], "dpa": estado["estado"],
            "clausula_notificacion": p["clausula_notificacion"], "riesgo": riesgo["nivel"],
            "prioridad": "alta" if alta else "normal", "accion": accion,
            "subencargados": [s["nombre"] for s in p["subencargados"]],
        })
    acciones.sort(key=lambda a: (a["prioridad"] != "alta", a["proveedor"]))
    return {
        "flujo": "brecha",
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "incidente": {"categoria": categoria, "descripcion": descripcion},
        "pasos": pasos,
        "acciones": acciones,
        "decision_humana": ("El DPO decide si notifica a la Autoridad Nacional de Protección de "
                            "Datos Personales (máx. 48 h, RLPDP art. 34) y a los titulares afectados."),
    }


def _tarea(p: dict) -> dict | None:
    d, r = p["dpa"], p["riesgo"]
    estado, dias = d["estado"], d["dias_restantes"]
    if estado == "sin_dpa":
        return {"prioridad": "alta", "motivo": "Sin DPA: formalizar el contrato de encargo (LPDP art. 30)."}
    if estado == "vencido":
        return {"prioridad": "alta", "motivo": f"DPA vencido hace {-dias} días: renovarlo."}
    if estado == "rechazado":
        return {"prioridad": "alta", "motivo": "DPA rechazado por Legal: negociar una nueva versión."}
    if estado == "por_vencer":
        return {"prioridad": "alta" if dias <= 30 else "media",
                "motivo": f"DPA vence en {dias} días: iniciar la renovación."}
    if estado == "pendiente_aprobacion":
        return {"prioridad": "media", "motivo": "DPA pendiente de aprobación legal."}
    if r["nivel"] in ("alto", "crítico"):
        return {"prioridad": "media",
                "motivo": f"Riesgo {r['nivel']}: revisar al proveedor cada {r['revision_meses']} meses."}
    return None


async def flujo_renovaciones(llamar: Llamar, log: Log | None = None) -> dict:
    pasos: list[dict] = []
    lista = await _paso(
        llamar, log, pasos, "Orquestador PIMS", "list_processors", {},
        lambda r: f"{len(r)} encargado(s) registrados",
    )
    tareas = []
    for p in lista:
        t = _tarea(p)
        if t:
            tareas.append({"proveedor": p["nombre"], "contacto": p["contacto"],
                           "riesgo": p["riesgo"]["nivel"], **t})
    tareas.sort(key=lambda t: (PRIORIDAD[t["prioridad"]], t["proveedor"]))
    return {"flujo": "renovaciones", "fecha": datetime.now().isoformat(timespec="seconds"),
            "pasos": pasos, "tareas": tareas,
            "decision_humana": "Asesoría Legal prioriza y aprueba cada renovación o nuevo DPA."}


def informe_flujo(res: dict) -> str:
    titulo = "brecha de seguridad" if res["flujo"] == "brecha" else "renovación de DPAs"
    lineas = [f"# Flujo multiagente: {titulo}", "", f"Fecha: {res['fecha']}", ""]
    if res["flujo"] == "brecha":
        inc = res["incidente"]
        lineas += [f"**Incidente:** {inc['descripcion'] or '—'} · datos afectados: {inc['categoria']}", ""]
    lineas += ["## Coordinación por MCP", "", "| # | Agente | Herramienta | Resultado |", "|---|---|---|---|"]
    for i, p in enumerate(res["pasos"], 1):
        args = ", ".join(f"{k}={v!r}" for k, v in p["argumentos"].items())
        lineas.append(f"| {i} | {p['agente']} | `{p['herramienta']}({args})` | {p['resultado']} |")
    lineas.append("")
    if res["flujo"] == "brecha":
        lineas += ["## Acciones propuestas", ""]
        if not res["acciones"]:
            lineas.append("Ningún encargado registrado trata esos datos.")
        for a in res["acciones"]:
            lineas += [f"- **{a['proveedor']}** (prioridad {a['prioridad']}, riesgo {a['riesgo']}, "
                       f"DPA {a['dpa']}, cláusula de notificación: {a['clausula_notificacion']}): "
                       f"{a['accion']} Contacto: {a['contacto'] or '—'}."]
    else:
        lineas += ["## Tareas", ""]
        for t in res["tareas"]:
            lineas.append(f"- **[{t['prioridad']}] {t['proveedor']}**: {t['motivo']}")
    lineas += ["", f"> Decisión humana: {res['decision_humana']}", ""]
    return "\n".join(lineas)


async def ejecutar_por_mcp(flujo: str, log: Log | None = None, **kwargs) -> dict:
    """Levanta el servidor MCP del agente como proceso hijo y ejecuta el flujo por stdio."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    from .config import ROOT

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "agente_terceros.cli", "mcp"], cwd=str(ROOT)
    )
    async with stdio_client(params) as (leer, escribir):
        async with ClientSession(leer, escribir) as sesion:
            await sesion.initialize()

            async def llamar(herramienta: str, argumentos: dict) -> Any:
                r = await sesion.call_tool(herramienta, argumentos)
                return json.loads(r.content[0].text)

            if flujo == "brecha":
                return await flujo_brecha(llamar, log=log, **kwargs)
            return await flujo_renovaciones(llamar, log=log)
