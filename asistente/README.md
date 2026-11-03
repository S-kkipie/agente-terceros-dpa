# Asistente: Auditor de Encargados (A7)

Definición del asistente del **Agente de Terceros (DPAs)** según las tres piezas que pide el TIF:
**identidad**, **instrucciones** y **conocimiento**. Sirve tal cual para montarlo como asistente
(Claude Project, GPT personalizado o Gem) y es la misma definición que usa el agente en código.

| Pieza | Archivo | Dónde vive en el código |
|---|---|---|
| Identidad | [`identidad.md`](identidad.md) | Panel web y servidor MCP `pims-terceros` |
| Instrucciones | [`instrucciones.md`](instrucciones.md) | `PROMPT` en `revisor.py`, `PROMPT_CONSULTA` en `agente.py` |
| Conocimiento | [`conocimiento.md`](conocimiento.md) | `data/raw/` → índice FAISS `data/index/`, `checklist.py` |
| Habilidades (skills) | [`../skills/`](../skills/) | CLI `agente-terceros revisar` y `orquestar` |
| Herramientas | MCP: `list_processors`, `check_dpa_status`, `evaluate_vendor`, `processors_in_breach` | `mcp_server.py` |

## De prompt a skill

1. **Prompt suelto (inicio):** "Revisa este contrato y dime si cumple la ley de protección de datos."
   Las respuestas variaban, no citaban artículos verificables y a veces inventaban plazos.
2. **Proceso reutilizable:** lo convertimos en un procedimiento fijo con 13 cláusulas mínimas
   (cada una con criterio, base normativa y peso), recuperación de normas por cláusula, una salida
   JSON con estado, cita literal y fundamento, verificación literal de las citas y un puntaje ponderado.
3. **Skill:** el procedimiento quedó empaquetado en [`skills/revisar-dpa/SKILL.md`](../skills/revisar-dpa/SKILL.md):
   una descripción que dice cuándo se activa, sus requisitos, pasos numerados, reglas y un ejemplo.
4. **Asistente:** la skill más la identidad, las instrucciones y el conocimiento de esta carpeta.
5. **Orquestación:** la skill [`brecha-encargados`](../skills/brecha-encargados/SKILL.md) coordina
   este asistente con el Agente de Incidentes por MCP.
