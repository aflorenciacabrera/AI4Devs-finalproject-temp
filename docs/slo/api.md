# SLO de firma

Un objetivo de nivel de servicio (SLO) para lo único que una persona nota si falla: **firmar**. Se mide con
los registros estructurados (`docs/observability.md`), sin infraestructura extra.

> **Estado:** los números de abajo son valores **iniciales**, elegidos sin datos de uso real. Hay que
> calibrarlos con las primeras semanas de registros de una instalación real.

## Qué se mide

Los **pedidos de firma**: los `http_request` cuya ruta termina en `/prepare` o `/complete` (firma individual
y en lote, por la API del integrador y por el widget).

| Indicador | Un pedido cuenta como bueno si… |
|---|---|
| **Disponibilidad** | el servidor respondió sin un error propio (estado menor que 500) |
| **Latencia** | además, respondió en 3 segundos o menos |

Un `4xx` es un pedido bueno: rechazar un certificado vencido (`422`) o un desafío ya usado (`409`) es el
servicio funcionando. Un `503` porque la autoridad de sellado de tiempo no responde (con
`FIRMADOC_TSA_REQUIRED=true`) sí cuenta como malo: para quien firma, no pudo firmar.

No entra en el indicador el tiempo que la persona tarda en ingresar el PIN: eso pasa en su PC, entre
`prepare` y `complete`.

## Objetivo y presupuesto de error

- **Objetivo:** el 99 % de los pedidos de firma, buenos en cada indicador.
- **Ventana:** 28 días corridos.
- **Presupuesto de error:** el 1 % restante. Con 2.000 pedidos de firma en la ventana, son **20 pedidos**
  que pueden fallar o tardar más de 3 segundos antes de incumplir.

El presupuesto es lo que permite decidir: mientras quede, se pueden hacer cambios con riesgo; si se agota,
lo siguiente que se hace es estabilidad.

## Alerta por tasa de consumo

No se avisa por cada error, sino cuando el presupuesto se gasta demasiado rápido:

| Situación | Tasa de consumo | Qué hacer |
|---|---|---|
| Se gasta 14 veces más rápido de lo sostenible durante 1 hora (el presupuesto de 28 días se iría en 2 días) | 14x | Atender ya |
| Se gasta 6 veces más rápido durante 6 horas | 6x | Revisar en el día |
| Menos de 1x | — | Nada: es el ritmo previsto |

## Cómo medirlo

```bash
python -m firmadoc.slo registros.log                 # informa
python -m firmadoc.slo --fail-on-breach registros.log  # termina con código 1 si no se cumple
docker compose logs demo --no-log-prefix | python -m firmadoc.slo
```

Salida de ejemplo:

```
SLO de firma: objetivo 99.00%, latencia hasta 3000 ms
  Disponibilidad  198/200 bien (99.00%) · tasa de consumo del presupuesto 1.0x
  Latencia        196/200 bien (98.00%) · tasa de consumo del presupuesto 2.0x
  Resultado: FUERA del objetivo en esta ventana
```

La herramienta mide la ventana que cubren los registros que recibe: para la alerta de 1 hora se le pasa la
última hora; para el objetivo, los 28 días. Con menos de 100 pedidos avisa que la muestra es chica.
Opciones: `--objective` (porcentaje) y `--latency-ms`.

## Lo que este SLO no cubre

- **Hoy la medición es manual**: nadie recibe un aviso. Automatizarla depende de dónde se guarden los
  registros (`docs/observability.md`).
- La entrega de **webhooks** al integrador, el **panel** y las consultas: no son pedidos de firma.
- Que el **agente local** y el token funcionen en la PC del firmante: el servidor no lo ve.
- Que la firma sea **válida**: eso lo garantizan las validaciones y las pruebas, no un indicador de tiempo.
