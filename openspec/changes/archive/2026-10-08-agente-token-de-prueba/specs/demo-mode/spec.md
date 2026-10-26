## ADDED Requirements

### Requirement: Token de prueba para firmar con el agente
El modo demostración SHALL generar una vez, en `data/demo/token/`, una AC de prueba (`ca.crt`) y un certificado de firmante con clave privada (`firmante.pem`) cuyo sujeto lleve el CUIL `20000000001` («Firmante de Prueba»), y SHALL reutilizarlos en arranques siguientes. SHALL armar un directorio de confianza propio (`data/demo/trust/`) con las anclas del repositorio más la AC de prueba y apuntar `FIRMADOC_TRUST_DIR` a él, sin modificar `backend/trust`. SHALL configurar al firmante del panel con ese nombre y CUIL para que la validación del certificado del token de prueba pase. La guía SHALL imprimir el comando del agente con token de software y el PIN `1234`.

#### Scenario: Primer arranque
- **WHEN** se prepara la demo en una carpeta vacía
- **THEN** existen `data/demo/token/ca.crt` y `firmante.pem`, el certificado está firmado por esa AC y lleva `CUIL 20000000001`, y `data/demo/trust/` contiene la AC de prueba

#### Scenario: Arranques siguientes
- **WHEN** se prepara la demo de nuevo sin `--reset`
- **THEN** la AC y el certificado son los mismos (misma huella)

#### Scenario: Guía
- **WHEN** arranca la demo
- **THEN** la guía muestra `firmadoc-agent run --software-token data/demo/token/firmante.pem --origin http://localhost:<puerto>` y el PIN `1234`

#### Scenario: Validación del certificado de prueba
- **WHEN** el agente de prueba presenta su certificado en `prepare` para una solicitud cargada desde el panel de la demo
- **THEN** el servidor lo acepta (cadena hasta la AC de prueba y CUIL del firmante del panel)
