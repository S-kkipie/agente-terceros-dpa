# Guía del equipo: Agente de Terceros (DPAs)

Todo lo necesario para correr el agente en una PC, presentarlo en 15 minutos y responder
preguntas. TIF de Auditoría de Sistemas (UNSA), 2.ª entrega.

- Repositorio: https://github.com/S-kkipie/agente-terceros-dpa
- Hoja de entrega (Moodle): `docs/entrega/hoja_entrega.pdf`
- Guion de demo minuto a minuto: `docs/entrega/guion_demo.html` (ábrelo en el navegador)
- Informe IEEE: `docs/informe/informe.pdf` · Diapositivas: `docs/diapos/diapos.pdf`

---

## 1. Qué es (en 30 segundos)

Es el **agente 7 de los 8** del PIMS multiagente basado en **ISO/IEC 27701:2025**. Gestiona a los
**encargados del tratamiento**, los proveedores que tratan datos personales por nosotros (nube,
planillas, pagos, mailing):

- **Revisa contratos de encargo (DPA)** contra 13 cláusulas mínimas (LPDP art. 30, RLPDP arts. 28-33
  y 36, RGPD art. 28) con citas literales del contrato y fundamento (fuente, artículo, página).
- **Evalúa el riesgo** del proveedor (probabilidad × impacto, matriz 4×4).
- **Controla vencimientos y subencargados**.
- **Apoya ante una brecha**: dice qué encargados tratan los datos afectados.
- **Toda decisión pasa por aprobación humana** (Asesoría Legal / DPO) y queda en una bitácora.

Controles ISO/IEC 27701:2025: **A.1.2.7** (contratos con encargados), **A.2.5.7** (divulgación de
subcontratistas), **A.2.5.8** (contratación de subencargados), **A.2.5.9** (cambio de subencargado).

---

## 2. Instalar y correr en tu PC

### Requisitos

| Programa | Para qué | Cómo instalar |
|---|---|---|
| Git | Clonar el repo | https://git-scm.com |
| uv | Python 3.12 y dependencias (lo hace solo) | Linux/macOS: `curl -LsSf https://astral.sh/uv/install.sh \| sh` · Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Ollama | Embeddings locales (búsqueda en las normas) | https://ollama.com/download |
| Clave de IA | El modelo que revisa contratos | Ver abajo |

### Clave de IA

El agente acepta varios proveedores. Lo más fácil para cada integrante:

- **Gemini gratis**: crea una clave en https://aistudio.google.com/apikey y ponla como `GOOGLE_API_KEY`,
  con `TERCEROS_LLM_PROVIDER=gemini`.
- **OpenRouter** (lo que usa el agente por defecto): `OPENROUTER_API_KEY`. La cuenta necesita
  **créditos cargados**: el límite de la clave no es saldo.
- **Sin internet**: `TERCEROS_LLM_PROVIDER=ollama` y `ollama pull qwen3:4b`. Es más lento.

Si el proveedor principal falla, el agente prueba solo Gemini y luego Ollama.
**Nunca subas el `.env` al repo ni compartas tu clave por chat.**

### Pasos

```bash
git clone https://github.com/S-kkipie/agente-terceros-dpa.git
cd agente-terceros-dpa
uv sync                                 # instala Python 3.12 y dependencias
ollama pull nomic-embed-text            # modelo de embeddings (una vez)
cp .env.example .env                    # Windows: copy .env.example .env
# edita .env y pon tu clave (ver arriba)
uv run agente-terceros diagnostico      # todo debe salir OK
uv run agente-terceros demo             # carga 4 proveedores de ejemplo (revisa 2 DPAs)
uv run agente-terceros web              # abre http://localhost:5000
```

> Ollama debe estar abierto (en Windows y macOS es una app; en Linux, `ollama serve`).

### Comandos útiles

| Comando | Qué hace |
|---|---|
| `uv run agente-terceros web --port 5001` | Interfaz web en otro puerto, si el 5000 está ocupado |
| `uv run agente-terceros revisar data/ejemplos/dpa_mailrapido_deficiente.txt` | Skill `revisar-dpa`: genera un informe `.md` |
| `uv run agente-terceros orquestar brecha --categoria salud` | Flujo multiagente por MCP ante una brecha |
| `uv run agente-terceros orquestar renovaciones` | Tareas por DPAs vencidos, por vencer o ausentes |
| `uv run agente-terceros mcp` | Servidor MCP (para el orquestador) |
| `uv run pytest` | Pruebas (no usan internet ni clave) |

---

## 3. Presentación (15 min, la hace un integrante al azar)

### La noche anterior

1. `git pull` y `uv sync`.
2. `uv run agente-terceros diagnostico` → todo OK.
3. Si la base está vacía: `uv run agente-terceros demo`.
4. **Calentar la caché** (en la clase saldrán al instante y sin costo; ayuda si falla internet):

   ```bash
   for f in data/ejemplos/*.txt; do uv run agente-terceros revisar "$f" -o /tmp/x.md; done
   ```

   En Windows (PowerShell): `Get-ChildItem data/ejemplos/*.txt | % { uv run agente-terceros revisar $_.FullName -o x.md }`

### 15 minutos antes

- Abrir Ollama, `uv run agente-terceros web` y el navegador en `http://localhost:5000` (Panel).
- Una terminal abierta en la carpeta del repo.
- La hoja de entrega o las diapositivas a mano.

### Guion

| Minuto | Qué mostrar |
|---|---|
| 0:00–1:30 | **Problema**: los encargados tratan datos por nosotros y la responsabilidad sigue siendo nuestra. Somos el agente A7 de los 8 del PIMS. |
| 1:30–3:00 | **Arquitectura y controles** (diagrama de la hoja): web y orquestador → agente con herramientas MCP → revisor, riesgo, base de datos; FAISS y Ollama locales; IA intercambiable. |
| 3:00–4:30 | **Panel**: 4 encargados, 2 críticos, 1 sin DPA, alerta de renovación, pendientes. Abrir MailRápido: riesgo 12/16 y sus factores. |
| 4:30–7:30 | **Revisar DPA en vivo**: proveedor LabClínico → subir `data/ejemplos/dpa_pagofacil_intermedio.txt` → %, cláusulas que faltan, **cita literal** y **fundamento**. |
| 7:30–8:30 | **Aprobación humana**: rechazar el DPA de MailRápido con comentario → Bitácora. |
| 8:30–11:00 | **Orquestación** en la terminal: `uv run agente-terceros orquestar brecha --categoria salud` (el Agente de Incidentes llama por MCP a 3 herramientas; el DPO decide notificar en 48 h). |
| 11:00–12:30 | **Skill y asistente**: mostrar `skills/revisar-dpa/SKILL.md` y la carpeta `asistente/`; correr `uv run agente-terceros revisar data/ejemplos/dpa_mailrapido_deficiente.txt`. |
| 12:30–13:30 | **Consulta normativa**: "¿En qué plazo debe el encargado notificar un incidente en el Perú?" → responde con citas (RLPDP art. 36). |
| 13:30–15:00 | **Resultados y cierre**: exactitud por cláusula 87,2 %, cumple/no cumple 92,3 %, 98,9 % de citas verificadas. Limitaciones. |

**Frase clave al revisar:** "si el modelo no puede citar literal el contrato, no lo damos por cumplido,
y nada se aprueba sin una persona".

### Si algo falla

- **Error de proveedor de IA** (sin saldo, 429): el agente cambia solo a Gemini u Ollama; el pie de la
  página dice cuál respondió.
- **Sin internet**: los contratos de ejemplo salen de la caché; para lo demás,
  `TERCEROS_LLM_PROVIDER=ollama uv run agente-terceros web`.
- **Puerto ocupado**: `uv run agente-terceros web --port 5001`.
- **"Ollama no responde"**: abrir la app de Ollama (o `ollama serve`) y repetir `diagnostico`.
- **Se cae todo**: mostrar las diapositivas (tienen capturas) y los informes de `data/salidas/`.

---

## 4. Preguntas probables

**¿Y si el modelo inventa?** Cada cita se verifica literal contra el contrato; si no aparece, la cláusula
no cuenta como cumplida. Además, nada surte efecto sin aprobación humana.

**¿Por qué no está el texto de la ISO/IEC 27701?** No es de libre acceso. Catalogamos los títulos de los
controles con una paráfrasis propia; la numeración de 2025 se infiere de la edición 2019 (Anexo F).

**¿Salen datos personales a internet?** La búsqueda es local (Ollama + FAISS). Al modelo solo va el texto
del contrato y fragmentos públicos de la norma, nunca la base de datos personales. Con Ollama, todo es local.

**¿Cómo se coordina con los otros 7 agentes?** Por el bus MCP: el servidor `pims-terceros` expone
`list_processors`, `check_dpa_status`, `evaluate_vendor` y `processors_in_breach`; el flujo de brecha
muestra al Agente de Incidentes usándolas.

**¿Qué es una skill aquí?** Un `SKILL.md` con descripción de activación (cuándo usarla), estructura y
pasos. Tenemos `revisar-dpa` y `brecha-encargados`.

**¿Y el asistente?** Identidad (rol, objetivo, límites), instrucciones (prompt de sistema) y conocimiento
(5 normas indexadas, 13 cláusulas, matriz de riesgo): carpeta `asistente/`.

**¿Por qué SQLite?** Por la demo en PC; el esquema es portable a la base PostgreSQL del PIMS.

**¿Cuánto cuesta?** Una revisión con Gemini 2.5 Flash por OpenRouter cuesta unos US$ 0,01 y tarda unos
15 s; repetirla sale de caché, gratis.

---

## 5. Detalles técnicos

### Arquitectura

```
Interfaz web (Flask + HTML/CSS/JS) ──REST──┐
Orquestador / Agente de Incidentes ──MCP──►  Agente de Terceros (agente.py)
                                             ├─ Revisor de DPA: 13 cláusulas, RAG, 1 llamada al LLM, citas verificadas
                                             ├─ Riesgo: matriz 4×4 determinista
                                             └─ Repositorio SQLite: proveedores, DPAs, subencargados, aprobaciones, bitácora
Revisor ── FAISS (978 fragmentos) ◄── Ollama nomic-embed-text (local)
Revisor ── Proveedor de IA: OpenRouter → Gemini → Ollama (o OpenAI / Anthropic)
```

### Cómo revisa un DPA

1. Extrae el texto del PDF/TXT.
2. Por cada cláusula recupera 4 fragmentos generales y 2 peruanos (consulta con vocabulario de la LPDP/RLPDP).
3. Una sola llamada al LLM devuelve, por cláusula: cumple / parcial / falta, cita, fundamento y recomendación.
4. Verifica literalmente cada cita; si no está en el contrato, un "cumple" baja a "parcial".
5. Calcula el cumplimiento ponderado (peso 3 esencial, 2 importante, 1 recomendable).
6. El DPA queda pendiente de aprobación legal.

### Corpus

LPDP (Ley 29733), RLPDP (D.S. 016-2024-JUS), RGPD, Directrices 07/2020 del CEPD y cláusulas tipo de la
Decisión (UE) 2021/915.

### Resultados de la evaluación

| Métrica | Valor |
|---|---|
| Exactitud por cláusula (3 contratos × 13 cláusulas × 3 corridas) | 87,2 % |
| Exactitud cumple / no cumple | 92,3 % |
| Estabilidad entre corridas | 89,7 % |
| Error medio del % de cumplimiento | 5,6 puntos |
| Citas que superan la verificación literal | 98,9 % |
| Cobertura de norma peruana en la recuperación | de 15 % a 69 % con la consulta peruana |

### Estructura del repo

| Carpeta | Contenido |
|---|---|
| `src/agente_terceros/` | Código: agente, revisor, riesgo, base de datos, LLM, orquestación, MCP, web |
| `skills/` | Skills `revisar-dpa` y `brecha-encargados` |
| `asistente/` | Identidad, instrucciones y conocimiento |
| `data/raw/` · `data/index/` | Normas y su índice FAISS |
| `data/ejemplos/` | 3 contratos de prueba |
| `eval/` | Evaluación y resultados |
| `docs/` | Hoja de entrega, guion, informe y diapositivas |
| `tests/` | Pruebas automáticas |

### Limitaciones

- Evaluación pequeña (3 contratos anotados por nosotros).
- El LLM no es determinista; lo mitigan la verificación literal y la aprobación humana.
- Numeración de ISO/IEC 27701:2025 inferida.
- Sin OCR para PDFs escaneados.
