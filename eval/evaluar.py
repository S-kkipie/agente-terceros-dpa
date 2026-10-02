"""Evaluación del Agente de Terceros.

1. Recuperación normativa por cláusula (13 consultas): Hit@k, MRR, P@k y cobertura
   de norma peruana, comparando búsqueda general frente a la mezcla Perú + general.
2. Revisión de DPAs: 3 contratos anotados por los autores × R corridas con Gemini.
   Exactitud por cláusula, exactitud binaria (cumple / no cumple), estabilidad entre
   corridas, error del % de cumplimiento, citas verificadas y latencia.

Uso: uv run python eval/evaluar.py [--corridas 3] [--solo-recuperacion]
Escribe eval/resultados/*.json y docs/metricas.tex.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from pathlib import Path

from agente_terceros.checklist import CLAUSULAS
from agente_terceros.config import ROOT, get_config
from agente_terceros.revisor import VALOR, _recuperar_normativa, llm_gemini, revisar_dpa
from agente_terceros.vectores import IndiceVectorial, embedder_ollama

RES = ROOT / "eval" / "resultados"
EDPB_CONTRATO = range(34, 49)  # sección del CEPD sobre el contrato de encargo (art. 28)

# Fragmentos relevantes por cláusula: (fuente, artículo/cláusula). EDPB-07/2020 cuenta
# como relevante si cae en las páginas que desarrollan el contrato de encargo.
RELEVANTES: dict[str, set[tuple[str, str]]] = {
    "objeto_duracion": {("RGPD", "28"), ("CCT-2021/915", "Cláusula 6"), ("LPDP", "30")},
    "instrucciones": {("RGPD", "28"), ("RGPD", "29"), ("CCT-2021/915", "Cláusula 7"),
                      ("LPDP", "30"), ("RLPDP", "30")},
    "confidencialidad": {("RGPD", "28"), ("CCT-2021/915", "Cláusula 7"), ("LPDP", "17")},
    "seguridad": {("RGPD", "28"), ("RGPD", "32"), ("CCT-2021/915", "Cláusula 7"),
                  ("LPDP", "16"), ("RLPDP", "30")},
    "subencargados": {("RGPD", "28"), ("CCT-2021/915", "Cláusula 7"), ("RLPDP", "31"),
                      ("RLPDP", "32"), ("RLPDP", "33")},
    "derechos_titulares": {("RGPD", "28"), ("CCT-2021/915", "Cláusula 8")},
    "notificacion_brechas": {("RGPD", "28"), ("RGPD", "33"), ("CCT-2021/915", "Cláusula 8"),
                             ("CCT-2021/915", "Cláusula 9"), ("RLPDP", "34"), ("RLPDP", "36")},
    "supresion_devolucion": {("RGPD", "28"), ("CCT-2021/915", "Cláusula 7"),
                             ("CCT-2021/915", "Cláusula 10"), ("LPDP", "30"),
                             ("RLPDP", "30"), ("RLPDP", "31")},
    "auditorias": {("RGPD", "28"), ("CCT-2021/915", "Cláusula 7"), ("RLPDP", "30")},
    "transferencias": {("RGPD", "44"), ("RGPD", "45"), ("RGPD", "46"),
                       ("CCT-2021/915", "Cláusula 7"), ("LPDP", "15"), ("RLPDP", "12"),
                       ("RLPDP", "13"), ("RLPDP", "14")},
    "limitacion_finalidad": {("RGPD", "28"), ("CCT-2021/915", "Cláusula 7"), ("LPDP", "30"),
                             ("RLPDP", "29"), ("RLPDP", "31"), ("RLPDP", "33")},
    "solicitudes_autoridad": {("RGPD", "28"), ("RLPDP", "30")},
    "eipd_asistencia": {("RGPD", "28"), ("RGPD", "35"), ("RGPD", "36"),
                        ("CCT-2021/915", "Cláusula 8"), ("RLPDP", "40")},
}

# Anotación de referencia de los autores (estado esperado por cláusula).
F, P, C = "falta", "parcial", "cumple"
GOLD = {
    "dpa_nubesegura_completo.txt": {c.id: C for c in CLAUSULAS},
    "dpa_pagofacil_intermedio.txt": {
        "objeto_duracion": C, "instrucciones": P, "confidencialidad": C, "seguridad": C,
        "subencargados": P, "derechos_titulares": F, "notificacion_brechas": C,
        "supresion_devolucion": P, "auditorias": F, "transferencias": F,
        "limitacion_finalidad": C, "solicitudes_autoridad": F, "eipd_asistencia": F,
    },
    "dpa_mailrapido_deficiente.txt": {
        "objeto_duracion": P, "instrucciones": F, "confidencialidad": P, "seguridad": P,
        "subencargados": F, "derechos_titulares": F, "notificacion_brechas": P,
        "supresion_devolucion": F, "auditorias": F, "transferencias": F,
        "limitacion_finalidad": F, "solicitudes_autoridad": F, "eipd_asistencia": F,
    },
}


def es_relevante(meta: dict, cid: str) -> bool:
    if meta["fuente"] == "EDPB-07/2020":
        return meta["pagina"] in EDPB_CONTRATO
    return (meta["fuente"], meta["articulo"]) in RELEVANTES[cid]


def evaluar_recuperacion(idx: IndiceVectorial, cfg) -> dict:
    estrategias = {
        "general": lambda c: [f for f, _ in idx.buscar(c.consulta, k=6)],
        "mixta": lambda c: _recuperar_normativa(idx, c, cfg),
    }
    res = {}
    for nombre, fn in estrategias.items():
        hits, rr, prec, peru, lat, detalle = [], [], [], [], [], []
        for c in CLAUSULAS:
            t0 = time.perf_counter()
            frags = fn(c)[:6]
            lat.append(time.perf_counter() - t0)
            rel = [es_relevante(f.meta, c.id) for f in frags]
            hits.append(any(rel))
            rr.append(next((1 / (i + 1) for i, r in enumerate(rel) if r), 0.0))
            prec.append(sum(rel) / len(frags))
            peru.append(any(r and f.meta["jurisdiccion"] == "Perú" for f, r in zip(frags, rel)))
            detalle.append({"clausula": c.id, "recuperados": [
                {"fuente": f.meta["fuente"], "articulo": f.meta["articulo"],
                 "pagina": f.meta["pagina"], "relevante": r} for f, r in zip(frags, rel)]})
        res[nombre] = {
            "hit": statistics.mean(hits), "mrr": statistics.mean(rr),
            "precision": statistics.mean(prec), "cobertura_peru": statistics.mean(peru),
            "latencia_s": statistics.mean(lat), "detalle": detalle,
        }
    return res


def evaluar_revision(idx: IndiceVectorial, embed, cfg, corridas: int) -> dict:
    llm = llm_gemini(cfg)
    pesos = {c.id: c.peso for c in CLAUSULAS}
    total_peso = sum(pesos.values())
    salida = {}
    for archivo, gold in GOLD.items():
        texto = (ROOT / "data" / "ejemplos" / archivo).read_text(encoding="utf-8")
        gold_pct = sum(pesos[k] * VALOR[v] for k, v in gold.items()) / total_peso * 100
        runs = []
        for _ in range(corridas):
            t0 = time.perf_counter()
            rev = revisar_dpa(texto, idx, embed, llm, cfg)
            runs.append({
                "latencia_s": time.perf_counter() - t0,
                "cumplimiento": rev.cumplimiento,
                "estados": {r.id: r.estado for r in rev.resultados},
                "con_evidencia": sum(bool(r.evidencia) for r in rev.resultados),
                "verificadas": sum(r.evidencia_verificada for r in rev.resultados),
            })
            print(f"  {archivo}: {rev.cumplimiento:.1f}% en {runs[-1]['latencia_s']:.1f} s")
        salida[archivo] = {"gold": gold, "gold_pct": gold_pct, "corridas": runs}
    return salida


def resumir_revision(rev: dict) -> dict:
    exact, binaria, estables, errores, lat, ev, ver = [], [], [], [], [], 0, 0
    confusion = Counter()
    por_contrato = {}
    for archivo, d in rev.items():
        gold, runs = d["gold"], d["corridas"]
        ex_c = []
        for run in runs:
            for cid, g in gold.items():
                p = run["estados"][cid]
                confusion[(g, p)] += 1
                exact.append(p == g)
                ex_c.append(p == g)
                binaria.append((p == "cumple") == (g == "cumple"))
            errores.append(abs(run["cumplimiento"] - d["gold_pct"]))
            lat.append(run["latencia_s"])
            ev += run["con_evidencia"]
            ver += run["verificadas"]
        for cid in gold:
            estables.append(len({run["estados"][cid] for run in runs}) == 1)
        por_contrato[archivo] = {
            "gold_pct": d["gold_pct"],
            "media_pct": statistics.mean(r["cumplimiento"] for r in runs),
            "min_pct": min(r["cumplimiento"] for r in runs),
            "max_pct": max(r["cumplimiento"] for r in runs),
            "exactitud": statistics.mean(ex_c),
        }
    return {
        "exactitud": statistics.mean(exact), "exactitud_binaria": statistics.mean(binaria),
        "estabilidad": statistics.mean(estables), "mae_pct": statistics.mean(errores),
        "latencia_s": statistics.mean(lat), "citas_verificadas": ver / ev if ev else 0,
        "confusion": {f"{g}->{p}": n for (g, p), n in sorted(confusion.items())},
        "por_contrato": por_contrato,
    }


def num(x: float, d: int = 3) -> str:
    return f"{x:.{d}f}".replace(".", "{,}")


def tabla_corpus(idx: IndiceVectorial) -> str:
    from agente_terceros.config import CORPUS

    filas = []
    for f in CORPUS:
        frags = [x for x in idx.fragmentos if x.meta["fuente"] == f.sigla]
        paginas = max(x.meta["pagina"] for x in frags)
        filas.append(f"{f.sigla} & {f.jurisdiccion} & {paginas if f.ruta.suffix == '.pdf' else '--'} & {len(frags)} \\\\")
    return "\n".join(filas)


def escribir_tex(
    rec: dict, rs: dict | None, idx: IndiceVectorial, corridas: int, rs_v1: dict | None = None
) -> None:
    g, m = rec["general"], rec["mixta"]
    n_frag = len(idx)
    lineas = [
        f"\\newcommand{{\\TablaCorpus}}{{{tabla_corpus(idx)}}}",
        "% Generado por eval/evaluar.py — no editar a mano",
        f"\\newcommand{{\\NumFragmentos}}{{{n_frag}}}",
        f"\\newcommand{{\\NumClausulas}}{{{len(CLAUSULAS)}}}",
        f"\\newcommand{{\\HitGen}}{{{num(g['hit'])}}}",
        f"\\newcommand{{\\MrrGen}}{{{num(g['mrr'])}}}",
        f"\\newcommand{{\\PGen}}{{{num(g['precision'])}}}",
        f"\\newcommand{{\\PeruGen}}{{{num(g['cobertura_peru'])}}}",
        f"\\newcommand{{\\HitMix}}{{{num(m['hit'])}}}",
        f"\\newcommand{{\\MrrMix}}{{{num(m['mrr'])}}}",
        f"\\newcommand{{\\PMix}}{{{num(m['precision'])}}}",
        f"\\newcommand{{\\PeruMix}}{{{num(m['cobertura_peru'])}}}",
        f"\\newcommand{{\\LatRec}}{{{num(m['latencia_s'] * 1000, 0)}}}",
    ]
    if rs:
        nombres = {"dpa_nubesegura_completo.txt": "Completo (NubeSegura)",
                   "dpa_pagofacil_intermedio.txt": "Intermedio (PagoFácil)",
                   "dpa_mailrapido_deficiente.txt": "Deficiente (MailRápido)"}
        filas = "\n".join(
            f"{nombres[a]} & {num(d['gold_pct'], 1)} & {num(d['media_pct'], 1)} & "
            f"{num(d['min_pct'], 1)}--{num(d['max_pct'], 1)} & {num(d['exactitud'] * 100, 1)}\\,\\% \\\\"
            for a, d in rs["por_contrato"].items()
        )
        lineas += [
            f"\\newcommand{{\\Corridas}}{{{corridas}}}",
            f"\\newcommand{{\\Exactitud}}{{{num(rs['exactitud'] * 100, 1)}\\,\\%}}",
            f"\\newcommand{{\\ExactitudBin}}{{{num(rs['exactitud_binaria'] * 100, 1)}\\,\\%}}",
            f"\\newcommand{{\\Estabilidad}}{{{num(rs['estabilidad'] * 100, 1)}\\,\\%}}",
            f"\\newcommand{{\\MaePct}}{{{num(rs['mae_pct'], 1)}}}",
            f"\\newcommand{{\\LatRev}}{{{num(rs['latencia_s'], 1)}}}",
            f"\\newcommand{{\\CitasVer}}{{{num(rs['citas_verificadas'] * 100, 1)}\\,\\%}}",
            f"\\newcommand{{\\TablaContratos}}{{{filas}}}",
        ]
        conf = rs["confusion"]
        for g_ in ("cumple", "parcial", "falta"):
            for p_ in ("cumple", "parcial", "falta"):
                lineas.append(
                    f"\\newcommand{{\\Conf{g_.capitalize()}{p_.capitalize()}}}{{{conf.get(f'{g_}->{p_}', 0)}}}"
                )
    if rs_v1:  # primera iteración del prompt (citas sin regla de literalidad estricta)
        lineas += [
            f"\\newcommand{{\\ExactitudVi}}{{{num(rs_v1['exactitud'] * 100, 1)}\\,\\%}}",
            f"\\newcommand{{\\ExactitudBinVi}}{{{num(rs_v1['exactitud_binaria'] * 100, 1)}\\,\\%}}",
            f"\\newcommand{{\\EstabilidadVi}}{{{num(rs_v1['estabilidad'] * 100, 1)}\\,\\%}}",
            f"\\newcommand{{\\MaePctVi}}{{{num(rs_v1['mae_pct'], 1)}}}",
            f"\\newcommand{{\\CitasVerVi}}{{{num(rs_v1['citas_verificadas'] * 100, 1)}\\,\\%}}",
        ]
    tex = "\n".join(lineas) + "\n"
    for destino in ("informe", "diapos"):
        d = ROOT / "docs" / destino
        d.mkdir(parents=True, exist_ok=True)
        (d / "metricas.tex").write_text(tex, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corridas", type=int, default=3)
    ap.add_argument("--solo-recuperacion", action="store_true")
    ap.add_argument("--desde-json", action="store_true", help="Solo regenera metricas.tex")
    args = ap.parse_args()

    cfg = get_config()
    embed = embedder_ollama(cfg)
    idx = IndiceVectorial.cargar(cfg.index_dir, embed)
    RES.mkdir(parents=True, exist_ok=True)

    if args.desde_json:
        rec = json.loads((RES / "recuperacion.json").read_text(encoding="utf-8"))
        rev = json.loads((RES / "revision.json").read_text(encoding="utf-8"))["crudo"]
        corridas = len(next(iter(rev.values()))["corridas"])
        v1 = RES / "revision_v1.json"
        rs_v1 = resumir_revision(json.loads(v1.read_text(encoding="utf-8"))["crudo"]) if v1.exists() else None
        escribir_tex(rec, resumir_revision(rev), idx, corridas, rs_v1)
        return

    rec = evaluar_recuperacion(idx, cfg)
    (RES / "recuperacion.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in rec.items():
        print(f"{k:8} Hit@6={v['hit']:.3f} MRR={v['mrr']:.3f} P@6={v['precision']:.3f} Perú={v['cobertura_peru']:.3f}")

    rs = None
    if not args.solo_recuperacion:
        rev = evaluar_revision(idx, embed, cfg, args.corridas)
        rs = resumir_revision(rev)
        (RES / "revision.json").write_text(json.dumps({"crudo": rev, "resumen": rs}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in rs.items() if k != "por_contrato"}, ensure_ascii=False, indent=1))
    escribir_tex(rec, rs, idx, args.corridas)


if __name__ == "__main__":
    main()
