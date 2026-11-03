"""Configuración central: rutas, modelos, parámetros y corpus normativo."""

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Fuente:
    """Documento normativo o metodológico del corpus."""

    archivo: str
    titulo: str
    sigla: str
    jurisdiccion: str
    url: str = ""

    @property
    def ruta(self) -> Path:
        return RAW_DIR / self.archivo


CORPUS: tuple[Fuente, ...] = (
    Fuente(
        "ley_29733_peru.pdf",
        "Ley N.º 29733, Ley de Protección de Datos Personales",
        "LPDP",
        "Perú",
        "https://www.minjus.gob.pe/wp-content/uploads/2013/04/LEY-29733.pdf",
    ),
    Fuente(
        "ds_016_2024_jus_reglamento.pdf",
        "D.S. N.º 016-2024-JUS, Reglamento de la Ley N.º 29733",
        "RLPDP",
        "Perú",
        "https://www.gob.pe/institucion/anpd/normas-legales/6554453-n-016-2024-jus",
    ),
    Fuente(
        "rgpd_2016_679_es.pdf",
        "Reglamento (UE) 2016/679 — Reglamento General de Protección de Datos",
        "RGPD",
        "Unión Europea",
        "https://www.boe.es/doue/2016/119/L00001-00088.pdf",
    ),
    Fuente(
        "edpb_07_2020_es.pdf",
        "CEPD, Directrices 07/2020 sobre los conceptos de responsable y encargado del tratamiento",
        "EDPB-07/2020",
        "Unión Europea",
        "https://www.edpb.europa.eu/system/files/2023-10/edpb_guidelines_202007_controllerprocessor_final_es.pdf",
    ),
    Fuente(
        "decision_2021_915_scc_art28_es.txt",
        "Decisión de Ejecución (UE) 2021/915 — Cláusulas contractuales tipo entre responsables y encargados",
        "CCT-2021/915",
        "Unión Europea",
        "https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32021D0915",
    ),
)


@dataclass(frozen=True)
class Config:
    index_dir: Path = ROOT / "data" / "index"
    db_path: Path = Path(os.getenv("TERCEROS_DB", str(ROOT / "data" / "terceros.db")))

    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    embedding_model: str = os.getenv("TERCEROS_EMBEDDING_MODEL", "nomic-embed-text")
    # Proveedor de IA: openrouter (por defecto, con Gemini) | gemini | openai (u OpenAI-compatible)
    # | anthropic | ollama.
    llm_provider: str = os.getenv("TERCEROS_LLM_PROVIDER", "openrouter").strip().lower()
    llm_model: str = os.getenv("TERCEROS_LLM_MODEL", "")  # vacío = modelo por defecto del proveedor
    llm_base_url: str = os.getenv("TERCEROS_LLM_BASE_URL", "")  # p. ej. OpenRouter, Groq, LM Studio
    # Proveedores de respaldo, en orden, si el principal falla (sin saldo, 429, red).
    llm_respaldo: tuple[str, ...] = tuple(
        x.strip().lower() for x in os.getenv("TERCEROS_LLM_RESPALDO", "gemini,ollama").split(",") if x.strip()
    )
    temperature: float = 0.1
    max_tokens: int = 8000  # tope de salida por llamada (controla el gasto)
    cache_dir: Path = ROOT / "data" / "cache_ia"  # respuestas ya pagadas, por hash del prompt
    gasto_path: Path = ROOT / "data" / "gasto_ia.json"

    tamano: int = 1000
    solape: int = 150
    top_k: int = 4  # fragmentos normativos por cláusula
    top_k_contrato: int = 3  # fragmentos del contrato por cláusula

    dias_alerta: int = 60  # aviso de vencimiento de DPAs


def get_config() -> Config:
    return Config()
