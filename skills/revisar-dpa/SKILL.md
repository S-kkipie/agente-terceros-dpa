---
name: revisar-dpa
description: Revisa un contrato de encargo de tratamiento de datos personales (DPA) frente a la Ley 29733, su Reglamento (D.S. 016-2024-JUS), el art. 28 del RGPD e ISO/IEC 27701:2025, y produce un informe de cumplimiento con citas literales y fundamento normativo. Úsala cuando alguien pida revisar, auditar o evaluar un contrato con un proveedor que trata datos personales por cuenta de la organización (encargado, tercero, subencargado, "data processing agreement", contrato de tercerización, hosting, nube, planillas, pasarela de pagos, mailing), o pregunte si ese contrato cumple la normativa de protección de datos.
---

# Revisar un contrato de encargo (DPA)

Skill del **Agente de Terceros (A7)** del PIMS multiagente ISO/IEC 27701:2025.
Controles: A.1.2.7 (contratos con encargados), A.2.5.7 (divulgación de subcontratistas),
A.2.5.8 (contratación de subencargados), A.2.5.9 (cambio de subencargado).

## Cuándo usarla

- "Revisa este contrato con el proveedor de nube."
- "¿Este DPA cumple la Ley 29733?"
- "¿Qué le falta al contrato de mailing para proteger los datos?"

**No** la uses para contratos sin datos personales, para evaluar un tratamiento propio
(eso es una EIPD, del Agente de Riesgos) ni para responder dudas generales de normativa
(usa `agente-terceros` → *Consulta normativa*).

## Requisitos

- Repositorio instalado (`uv sync`) y Ollama en ejecución con `nomic-embed-text`.
- Proveedor de IA configurado en `.env` (OpenRouter por defecto; respaldo Gemini → Ollama).
- Comprueba todo con:

```bash
uv run agente-terceros diagnostico
```

## Pasos

1. **Recibir el contrato** en PDF o TXT. Si el PDF es escaneado (sin texto), pide una versión con texto: el agente no tiene OCR.
2. **Ejecutar la revisión**:

   ```bash
   uv run agente-terceros revisar ruta/al/contrato.pdf -o informe.md
   ```

   El agente recupera, por cada una de las 13 cláusulas mínimas (`referencias/clausulas.md`),
   fragmentos de la LPDP, el RLPDP, el RGPD, las Directrices 07/2020 del CEPD y las cláusulas
   tipo de la Decisión (UE) 2021/915 (FAISS + embeddings locales). Luego pide al LLM, en una sola
   llamada, el estado de cada cláusula con su cita literal.
3. **Leer el informe** (`informe.md`): cumplimiento ponderado (%), resumen y, de lo más grave a
   lo menos grave, cada cláusula con estado, cita, recomendación y fundamento (fuente, artículo y página).
4. **Señalar las citas no verificadas**: si una cita no aparece literal en el contrato, el agente
   la marca y nunca la cuenta como "cumple". Recomiéndale al usuario revisarla a mano.
5. **Registrar y someter a aprobación**: para que el DPA quede en el registro del PIMS, súbelo
   desde la interfaz web (`uv run agente-terceros web` → *Revisar DPA*) o con
   `POST /api/proveedores/<id>/dpa`. Queda **pendiente de aprobación legal**: nunca lo des por
   aprobado tú mismo.
6. **Responder al usuario** con el porcentaje, las cláusulas que faltan (priorizando las de peso 3)
   y las recomendaciones concretas. Termina indicando que la decisión corresponde a Asesoría Legal o al DPO.

## Reglas

- Cita solo lo que el informe trae; no inventes artículos, plazos ni cláusulas.
- En el Perú rigen la LPDP y el RLPDP; el RGPD, el CEPD y las cláusulas tipo de la UE son referencia comparada.
- La numeración de ISO/IEC 27701:2025 es inferida de la edición 2019: indícalo si la citas en un informe formal.

## Ejemplo

Entrada: `data/ejemplos/dpa_mailrapido_deficiente.txt`
Salida esperada: cumplimiento cercano al 20 %, con "falta" en subencargados, supresión al terminar
el servicio y prohibición de fines propios. Recomendación clave: exigir autorización previa de
subencargados (RLPDP art. 32) y la supresión evidenciada (RLPDP arts. 30.4 y 31.2).
