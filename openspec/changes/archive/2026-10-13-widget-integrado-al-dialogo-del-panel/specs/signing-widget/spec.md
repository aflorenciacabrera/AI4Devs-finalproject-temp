## ADDED Requirements

### Requirement: Apariencia integrada en el anfitrión
El widget SHALL verse como parte del diálogo o la página que lo embebe: SHALL NOT dibujar un marco propio (barra de marca, borde, fondo o radio de tarjeta) y su fondo SHALL ser transparente, con los botones de acción al pie sobre una línea. SHALL aceptar `?theme=light|dark` en la URL de firma (antes del fragmento) para usar el tema del anfitrión; sin ese parámetro SHALL seguir el esquema de colores del sistema. Cada pantalla SHALL limitarse al título, el documento o los datos de la firma, las opciones y las acciones, sin leyendas aclaratorias redundantes: se conservan solo los textos que orientan una acción (dónde ingresar el PIN, qué comprobar si falta el agente, el motivo de un rechazo, el enlace al servicio remoto).

#### Scenario: Sin marco propio
- **WHEN** el widget se muestra dentro del diálogo del panel
- **THEN** no aparece ninguna barra con la marca ni un borde o fondo de tarjeta, y el fondo es el del diálogo

#### Scenario: Tema del anfitrión
- **WHEN** la URL de firma lleva `?theme=dark`
- **THEN** el widget usa sus colores oscuros; con `?theme=light`, los claros; sin el parámetro, los del sistema

#### Scenario: Sin aclaraciones de más
- **WHEN** se recorre la elección del método, la confirmación, la espera del PIN y el resultado
- **THEN** no hay leyendas al pie ni avisos que repitan lo que ya dicen el título, el subtítulo o los datos visibles
