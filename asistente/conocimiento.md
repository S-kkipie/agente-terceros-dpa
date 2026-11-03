# Conocimiento

## Base normativa (RAG, `data/raw/` → índice FAISS `data/index/`)

| Sigla | Documento | Jurisdicción | Para qué lo usa el asistente |
|---|---|---|---|
| LPDP | Ley N.º 29733, Ley de Protección de Datos Personales | Perú | Art. 30: prestación de servicios de tratamiento |
| RLPDP | D.S. N.º 016-2024-JUS, Reglamento de la Ley 29733 | Perú | Arts. 28-33 (tercerización, encargo y subcontratación), 34 y 36 (incidentes) |
| RGPD | Reglamento (UE) 2016/679 | Unión Europea | Art. 28: contenido mínimo del contrato de encargo |
| EDPB-07/2020 | Directrices 07/2020 del CEPD sobre responsable y encargado | Unión Europea | Interpretación del art. 28 |
| CCT-2021/915 | Decisión de Ejecución (UE) 2021/915, cláusulas contractuales tipo | Unión Europea | Redacción modelo de cada obligación |

978 fragmentos de hasta 1000 caracteres, con fuente, artículo o cláusula y página, vectorizados
con `nomic-embed-text` (Ollama, local) en un índice FAISS de similitud coseno.

## Conocimiento estructurado

- **13 cláusulas mínimas** con criterio, base normativa, controles y peso: `src/agente_terceros/checklist.py` ([tabla](../skills/revisar-dpa/referencias/clausulas.md)).
- **Controles ISO/IEC 27701:2025** de las tablas A.1 y A.2: catálogo propio de títulos y paráfrasis (la norma no es de libre acceso; numeración inferida de la edición 2019).
- **Matriz de riesgo 4×4** (AEPD, NTP-ISO 31000): `src/agente_terceros/riesgo.py`.

## Conocimiento operativo (base de datos del PIMS)

Proveedores, DPAs con su vencimiento y revisión, subencargados, aprobaciones pendientes y
bitácora de auditoría: `data/terceros.db`, consultables mediante las herramientas MCP.
