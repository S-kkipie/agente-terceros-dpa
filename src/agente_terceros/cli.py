"""CLI: agente-terceros ingest | demo | web | mcp."""

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="agente-terceros", description="Agente de Terceros (DPAs) — PIMS ISO/IEC 27701")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest", help="Construye el índice FAISS desde data/raw (Ollama nomic-embed-text)")
    sub.add_parser("demo", help="Carga el escenario de demostración (revisa 2 DPAs con Gemini)")
    web = sub.add_parser("web", help="Levanta la interfaz web Flask")
    web.add_argument("--port", type=int, default=5000)
    sub.add_parser("mcp", help="Servidor MCP por stdio (list_processors, check_dpa_status, evaluate_vendor)")
    rev = sub.add_parser("revisar", help="Revisa un contrato de encargo (PDF/TXT) y genera un informe Markdown")
    rev.add_argument("contrato", help="Ruta del contrato (PDF o TXT)")
    rev.add_argument("-o", "--salida", help="Archivo .md de salida (por defecto <contrato>.revision.md)")
    rev.add_argument("--json", action="store_true", help="Imprime la revisión completa en JSON")
    sub.add_parser("diagnostico", help="Comprueba Ollama, índice FAISS y proveedor de IA antes de una demo")
    orq = sub.add_parser("orquestar", help="Flujo multiagente por MCP: brecha | renovaciones")
    orq.add_argument("flujo", choices=["brecha", "renovaciones"])
    orq.add_argument("--categoria", default="salud", help="Datos o sistema afectado (flujo brecha)")
    orq.add_argument("--descripcion", default="Acceso no autorizado a datos de salud detectado por el SIEM")
    args = p.parse_args(argv)

    if args.cmd == "orquestar":
        _orquestar(args)
        return

    if args.cmd == "diagnostico":
        from .config import get_config
        from .reporte import diagnosticar

        resultados = diagnosticar(get_config())
        for nombre, ok, detalle in resultados:
            print(f"  {'OK ' if ok else 'FALLA'}  {nombre:<26} {detalle}")
        sys.exit(0 if all(ok for _, ok, _ in resultados) else 1)

    if args.cmd == "revisar":
        _revisar(args)
        return

    if args.cmd == "ingest":
        from .config import get_config
        from .vectores import construir_indice, embedder_ollama

        cfg = get_config()
        idx = construir_indice(cfg, embedder_ollama(cfg))
        print(f"Índice listo: {len(idx)} fragmentos en {cfg.index_dir}")
        return

    from .app import crear_agente_real

    agente = crear_agente_real()
    if args.cmd == "demo":
        from .demo import sembrar_demo

        print("Escenario cargado." if sembrar_demo(agente) else "La base ya tiene datos; no se cargó nada.")
    elif args.cmd == "web":
        from .app import create_app

        create_app(agente).run(port=args.port, debug=False)
    elif args.cmd == "mcp":
        from .mcp_server import crear_servidor

        crear_servidor(agente).run("stdio")


def _orquestar(args) -> None:
    import asyncio
    from datetime import datetime

    from .config import ROOT
    from .orquestacion import ejecutar_por_mcp, informe_flujo

    n = 0

    def log(paso: dict) -> None:
        nonlocal n
        n += 1
        args_txt = ", ".join(f"{k}={v!r}" for k, v in paso["argumentos"].items())
        print(f"  [{n}] {paso['agente']} → MCP {paso['herramienta']}({args_txt})")
        print(f"      ⇒ {paso['resultado']}")

    print(f"Flujo «{args.flujo}»: el servidor MCP del Agente de Terceros se levanta por stdio…\n")
    kwargs = {"categoria": args.categoria, "descripcion": args.descripcion} if args.flujo == "brecha" else {}
    res = asyncio.run(ejecutar_por_mcp(args.flujo, log=log, **kwargs))
    md = informe_flujo(res)
    print("\n" + md[md.index("## Acciones") if "## Acciones" in md else md.index("## Tareas"):])
    salida = ROOT / "data" / "salidas" / f"flujo_{args.flujo}_{datetime.now():%Y%m%d_%H%M%S}.md"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(md, encoding="utf-8")
    print(f"Informe: {salida}")


def _revisar(args) -> None:
    import json
    from pathlib import Path

    from .app import extraer_texto, llm_real
    from .config import get_config
    from .llm import RegistroGasto, descripcion
    from .reporte import informe_markdown
    from .revisor import revisar_dpa
    from .vectores import IndiceVectorial, construir_indice, embedder_ollama

    ruta = Path(args.contrato)
    if not ruta.exists():
        sys.exit(f"No existe el archivo: {ruta}")
    cfg = get_config()
    embed = embedder_ollama(cfg)
    indice = cfg.index_dir / "normativa.faiss"
    normativa = IndiceVectorial.cargar(cfg.index_dir, embed) if indice.exists() else construir_indice(cfg, embed)
    print(f"Revisando {ruta.name} con {descripcion(cfg)}…", file=sys.stderr)
    revision = revisar_dpa(extraer_texto(ruta.name, ruta.read_bytes()), normativa, embed, llm_real(cfg), cfg)
    if args.json:
        print(json.dumps(revision.to_dict(), ensure_ascii=False, indent=1))
        return
    salida = Path(args.salida) if args.salida else ruta.with_suffix(".revision.md")
    salida.write_text(informe_markdown(revision.to_dict(), ruta.name), encoding="utf-8")
    print(f"Cumplimiento: {revision.cumplimiento:.1f} %  ·  informe: {salida}")
    g = RegistroGasto(cfg.gasto_path).resumen()
    print(f"Gasto acumulado en IA: US$ {g['usd']:.4f} en {g['llamadas']} llamadas", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
