#!/usr/bin/env bash
# Regenera metricas.tex desde eval/resultados y compila informe + diapositivas.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python eval/evaluar.py --desde-json 2>/dev/null
cd docs/informe
pdflatex -interaction=nonstopmode -halt-on-error informe.tex > /dev/null
bibtex informe > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error informe.tex > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error informe.tex > /dev/null
cd ../diapos
pdflatex -interaction=nonstopmode -halt-on-error diapos.tex > /dev/null
pdflatex -interaction=nonstopmode -halt-on-error diapos.tex > /dev/null
echo "OK: docs/informe/informe.pdf, docs/diapos/diapos.pdf"
