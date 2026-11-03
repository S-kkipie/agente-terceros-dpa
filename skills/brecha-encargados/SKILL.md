---
name: brecha-encargados
description: Ante una brecha o incidente de seguridad que afecta datos personales, identifica qué encargados del tratamiento (proveedores, terceros) tratan los datos o sistemas afectados, revisa si su contrato les obliga a notificar y su nivel de riesgo, y prepara las acciones para el DPO. Úsala cuando se reporte un incidente, una filtración, un acceso no autorizado o un ransomware que involucre datos de salud, económicos, de identificación u otros, o un sistema (ERP, CRM, planillas), y haya que saber qué terceros están implicados.
---

# Encargados implicados en una brecha

Skill de orquestación del PIMS multiagente: el **Agente de Incidentes** coordina al
**Agente de Terceros** por el bus MCP. Apoya los controles A.2.2.6 (información al cliente) y
A.2.5.7 (subcontratistas) de ISO/IEC 27701:2025 y los arts. 34 y 36 del RLPDP.

## Pasos

1. **Precisar qué se vio afectado**: la categoría de datos (salud, económicos, identificación…)
   o el sistema (ERP, CRM, planillas). Si el usuario da ambos, ejecuta el flujo con cada uno.
2. **Ejecutar el flujo multiagente** (levanta el servidor MCP del Agente de Terceros por stdio):

   ```bash
   uv run agente-terceros orquestar brecha --categoria salud --descripcion "Acceso no autorizado al ERP"
   ```

   El Agente de Incidentes llama a estas herramientas MCP:
   - `processors_in_breach(termino)`: qué encargados tratan esos datos o ese sistema y si su DPA tiene cláusula de notificación;
   - `check_dpa_status(proveedor_id)`: si el DPA está vigente, vencido, pendiente o ausente;
   - `evaluate_vendor(proveedor_id)`: riesgo del encargado (probabilidad × impacto).
3. **Priorizar**: prioridad alta si no hay DPA vigente, si el contrato no garantiza la notificación
   o si el riesgo es alto o crítico.
4. **Entregar el plan** (`data/salidas/flujo_brecha_*.md`): a quién contactar, qué exigirle
   (informe inmediato, RLPDP art. 36) y qué subencargados podrían estar involucrados.
5. **Decisión humana**: el DPO decide si notifica a la Autoridad Nacional de Protección de Datos
   Personales (máx. 48 h, RLPDP art. 34) y a los titulares. La skill no notifica a nadie por su cuenta.

## Variante: renovaciones

```bash
uv run agente-terceros orquestar renovaciones
```

El orquestador revisa todos los encargados (`list_processors`) y genera tareas por DPAs ausentes,
vencidos, por vencer, pendientes o de riesgo alto.
