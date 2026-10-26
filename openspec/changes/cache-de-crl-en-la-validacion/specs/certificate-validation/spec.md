## ADDED Requirements

### Requirement: Reutilización de las CRL descargadas
Las CRL que una validación obtiene por red SHALL conservarse en memoria, compartidas por todo el proceso del servidor, y SHALL entregarse como CRL locales a las validaciones siguientes mientras estén vigentes (`next_update` posterior al momento de la validación), de modo que una misma CRL no se descargue más de una vez por proceso mientras esté vigente. Una CRL vencida SHALL descartarse y, si la consulta por red está habilitada, SHALL volver a obtenerse. Dos copias idénticas de una CRL (por ejemplo, desde dos puntos de distribución) SHALL guardarse una sola vez. Las CRL de `FIRMADOC_CRL_DIR` SHALL seguir aplicándose además de las de la caché.

#### Scenario: Segunda validación sin red
- **WHEN** una validación con consulta por red obtuvo la CRL de la AC y después otra validación de un certificado de la misma AC corre sin acceso a la red
- **THEN** la segunda validación usa la CRL en memoria y determina la revocación (un certificado revocado se rechaza con `certificate_revoked`; uno válido queda `good`)

#### Scenario: CRL vencida
- **WHEN** la CRL en memoria tiene `next_update` anterior al momento de la validación
- **THEN** no se usa: la validación la obtiene de nuevo si la red está habilitada o, si no, el estado queda indeterminado

#### Scenario: Sin duplicados
- **WHEN** la misma CRL llega dos veces (dos puntos de distribución)
- **THEN** la caché la guarda una sola vez
