import asyncio
import json
from datetime import date, timedelta

import pytest

from agente_terceros.agente import Agente
from agente_terceros.db import Repositorio
from agente_terceros.mcp_server import crear_servidor
from agente_terceros.orquestacion import flujo_brecha, flujo_renovaciones, informe_flujo
from agente_terceros.vectores import IndiceVectorial
from tests.test_agente import PROV, llm_falso


@pytest.fixture
def llamar(tmp_path, embed):
    """Cliente MCP en proceso: llama a las herramientas del servidor real."""
    agente = Agente(Repositorio(tmp_path / "o.db"), IndiceVectorial(embed), embed, llm_falso)
    repo = agente.repo
    lab = repo.crear_proveedor({**PROV, "nombre": "LabClínico", "incidentes_12m": 2})
    nube = repo.crear_proveedor({**PROV, "nombre": "NubeSegura", "sistemas": ["ERP"]})
    repo.registrar_dpa(nube, "dpa.txt", "2026-01-01", (date.today() + timedelta(days=20)).isoformat(), 95.0,
                       {"resultados": [{"id": "notificacion_brechas", "estado": "cumple",
                                        "evidencia": "notificará en 24 horas"}]})
    repo.resolver_aprobacion(repo.pendientes()[0]["id"], True, "Legal", "")
    repo.crear_proveedor({**PROV, "nombre": "Mailer", "categorias_datos": ["contacto"], "sistemas": ["CRM"],
                          "datos_sensibles": False})
    srv = crear_servidor(agente)

    async def _llamar(herramienta: str, argumentos: dict):
        r = await srv.call_tool(herramienta, argumentos)
        return json.loads(r.content[0].text)

    return _llamar


def test_flujo_brecha_coordina_herramientas_y_prioriza(llamar):
    pasos = []
    res = asyncio.run(flujo_brecha(llamar, "salud", "Acceso no autorizado al ERP", log=pasos.append))
    nombres = {a["proveedor"]: a for a in res["acciones"]}
    assert set(nombres) == {"LabClínico", "NubeSegura"}
    # Sin DPA ni cláusula de notificación: prioridad alta.
    assert nombres["LabClínico"]["prioridad"] == "alta"
    assert nombres["NubeSegura"]["prioridad"] == "normal"
    herramientas = [p["herramienta"] for p in res["pasos"]]
    assert herramientas[0] == "processors_in_breach"
    assert herramientas.count("check_dpa_status") == 2 and herramientas.count("evaluate_vendor") == 2
    assert len(pasos) == len(res["pasos"])  # se informa cada paso en vivo
    assert "48" in res["decision_humana"]


def test_flujo_brecha_sin_encargados_implicados(llamar):
    res = asyncio.run(flujo_brecha(llamar, "biométricos"))
    assert res["acciones"] == [] and len(res["pasos"]) == 1


def test_flujo_renovaciones_genera_tareas_ordenadas(llamar):
    res = asyncio.run(flujo_renovaciones(llamar))
    tareas = {t["proveedor"]: t for t in res["tareas"]}
    assert tareas["LabClínico"]["motivo"].startswith("Sin DPA")
    assert "vence en 20 días" in tareas["NubeSegura"]["motivo"]
    assert res["tareas"][0]["prioridad"] == "alta"


def test_informe_flujo_en_markdown(llamar):
    res = asyncio.run(flujo_brecha(llamar, "salud", "Acceso no autorizado al ERP"))
    md = informe_flujo(res)
    assert md.startswith("# Flujo multiagente: brecha de seguridad")
    assert "processors_in_breach" in md and "LabClínico" in md
