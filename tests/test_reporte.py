from dataclasses import replace

from agente_terceros.config import get_config
from agente_terceros.reporte import diagnosticar, informe_markdown

REVISION = {
    "cumplimiento": 41.9,
    "resumen": "Contrato incompleto.",
    "resultados": [
        {"id": "subencargados", "titulo": "Subencargados: autorización previa", "peso": 3,
         "rgpd": "Art. 28.2", "peru": "RLPDP art. 32", "iso": ["A.2.5.8"], "estado": "falta",
         "evidencia": "", "evidencia_verificada": False, "fundamento": [1],
         "recomendacion": "Exigir autorización previa."},
        {"id": "instrucciones", "titulo": "Instrucciones documentadas", "peso": 3,
         "rgpd": "Art. 28.3.a", "peru": "LPDP art. 30", "iso": ["A.2.2.3"], "estado": "cumple",
         "evidencia": "siguiendo instrucciones documentadas", "evidencia_verificada": True,
         "fundamento": [1], "recomendacion": ""},
    ],
    "fuentes": {"1": {"etiqueta": "RLPDP, art. 32, p. 21", "titulo": "Reglamento", "texto": "..."}},
}


def test_informe_markdown_resume_y_prioriza_lo_que_falta():
    md = informe_markdown(REVISION, "dpa.pdf")
    assert md.startswith("# Revisión del contrato de encargo: dpa.pdf")
    assert "41.9 %" in md
    assert md.index("Subencargados") < md.index("Instrucciones documentadas")
    assert "Exigir autorización previa." in md
    assert "RLPDP, art. 32, p. 21" in md
    assert "pendiente de aprobación" in md.lower()


class R:
    def __init__(self, datos, ok=True):
        self.datos, self.ok = datos, ok

    def json(self):
        return self.datos


def test_diagnostico_detecta_ollama_modelo_indice_y_clave(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "agente_terceros.reporte.requests.get",
        lambda url, timeout=None, headers=None: R({"models": [{"name": "nomic-embed-text:latest"}]}),
    )
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    cfg = replace(get_config(), llm_provider="gemini", llm_model="")
    res = {nombre: ok for nombre, ok, _ in diagnosticar(cfg)}
    assert res["Ollama en ejecución"] and res["Modelo de embeddings"]
    assert res["Índice FAISS"] and res["Clave del proveedor de IA"]


def test_diagnostico_falla_sin_ollama_ni_clave(monkeypatch, tmp_path):
    import requests

    def caido(url, timeout=None, headers=None):
        raise requests.ConnectionError("rechazada")

    monkeypatch.setattr("agente_terceros.reporte.requests.get", caido)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = replace(get_config(), llm_provider="anthropic", index_dir=tmp_path)
    res = {nombre: (ok, det) for nombre, ok, det in diagnosticar(cfg)}
    assert res["Ollama en ejecución"][0] is False and "ollama serve" in res["Ollama en ejecución"][1]
    assert res["Índice FAISS"][0] is False
    assert res["Clave del proveedor de IA"][0] is False
    assert "ANTHROPIC_API_KEY" in res["Clave del proveedor de IA"][1]


def test_diagnostico_muestra_saldo_de_openrouter(monkeypatch):
    def get(url, timeout=None, headers=None):
        if url.endswith("/key"):
            return R({"data": {"limit": 5, "limit_remaining": 4.87, "usage": 0.13}})
        return R({"models": [{"name": "nomic-embed-text:latest"}]})

    monkeypatch.setattr("agente_terceros.reporte.requests.get", get)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-x")
    cfg = replace(get_config(), llm_provider="openrouter", llm_model="")
    res = {nombre: (ok, det) for nombre, ok, det in diagnosticar(cfg)}
    assert res["Saldo de OpenRouter"] == (True, "US$ 4.87 de 5.00 disponibles")
