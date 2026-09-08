# ZoneGo — Plan de ejecución

**ETHOnline 2026 · Vía From Scratch · Base Sepolia · Equipo de cuatro**
Estado al **lunes 7 de septiembre — día 4**. Cierre: domingo 13, 12:00 ET.

Cada día cierra con un hito verificable. Si no se puede demostrar, el día no está
cerrado.

---

## El producto

El vecino busca algo cerca, camina hasta el local, escanea un QR y cobra. El
comercio paga solo cuando un humano único verificado cruza su puerta, y puede
auditar cada pago contra la cadena sin confiar en nosotros.

**La decisión que sostiene todo:** el comercio firma la visita con EIP-712 desde
su dispositivo, el vecino envía esa firma al contrato, y el contrato la verifica
en cadena. Nuestro servidor paga el gas por comodidad, no por autoridad. Si
desaparece, el vecino manda la misma firma él mismo y cobra igual.

Tres patrocinadores, ninguno removible: **World** (humano único), **Privy**
(billeteras sin frase semilla), **The Graph** (historial auditable).

---

## Los cuatro roles

| Persona | Dominio | Es dueño de | Entrega al equipo |
|---|---|---|---|
| **Sebastián** | Contratos y Web3 | `CampaignVault`, `VisitRegistry`, `FraudOracle`, verificación EIP-712, integración World ID, tests de Foundry | ABIs, direcciones desplegadas, tests en verde |
| **Lucio** | Servicios e infraestructura | API FastAPI, subgraph, servicio de épocas y árbol de Merkle, despliegue, monitoreo, CI | Endpoints documentados y URL del subgraph |
| **Edmer** | Ciencia de datos | Generador sintético, rasgos, modelo de fraude, clasificador de rubro, simulación de ataques, métricas | Modelo servido y tabla de métricas reproducible |
| **David** | Frontend y producto | App del vecino, panel del comercio, integración Privy, escáner QR, flujo de World | Demo navegable y las capturas del envío |

**Frontera Sebastián / Lucio.** Todo lo que compila a bytecode es de Sebastián.
Todo lo que corre en un servidor es de Lucio. El subgraph es de Lucio porque es
TypeScript y consultas, no Solidity.

**La regla que evita el bloqueo.** El esquema de eventos está congelado en
`schema/events.md` y nadie lo cambia sin acuerdo de los cuatro. Con el esquema
fijo, Edmer entrena contra la forma exacta del dato real, David construye contra
el servidor simulado y Lucio arma el subgraph en paralelo al contrato.

---

## Estado real

### Cadena — Base Sepolia, bloques 46522139–46522140

```
CampaignVault    0xf4ADec71da03c6595CF4624f7d4573C9EDb753B0
VisitRegistry    0xD33f2e26f11Fe011835D791EbA1BFE123479998A
FraudOracle      0x5157504d3a9683Ca953EF5db1255dE619E110A9B
```

### Subgraph — desplegado y consultable

```
https://api.studio.thegraph.com/query/1758817/zone-go/v0.0.1
```

Diez entidades, tres fuentes de datos, indexando desde el bloque 46522139.

### Ramas

| Rama | Commits sobre `main` | Contenido |
|---|---|---|
| `feat/api-base` | 57 | API con 12 endpoints, 164 tests, subgraph |
| `feat/contracts-skeleton` | 11 | Tres contratos, desplegados, 4 tests |
| `feat/data-scientist` | 2 | Generador, esquema de eventos, entrenamiento |
| `main` | — | **Un solo archivo: `README.md`** |

---

## Días 1 a 4 — cerrado

### Sebastián
- Repositorio público, Foundry, interfaces y eventos de los tres contratos.
- `struct` EIP-712 de la visita y su typehash.
- `CampaignVault`: `createCampaign`, `fund`, `withdraw`, desplegado.
- `VisitRegistry.claim`: verifica en cadena la firma del comercio, la vigencia,
  el nonce de un solo uso y el tope diario. Curva 100/50/25/0 por semana,
  calculada por el contrato.
- Cuatro tests: nonce reusado, montos de la curva, firma vencida, firmante
  equivocado.
- `CampaignCreated` emite geohash y radius. Los tres contratos redesplegados,
  `FraudOracle` incluido en `DeployAll.s.sol`.

### Lucio
- CI en GitHub Actions con `pytest` en cada push y cada PR.
- API FastAPI: `/health`, `/search` con radio de 1/5/10 km, `/campaigns`,
  `/qr/sign`, `/visits/claim`, `/score`, `/leaderboard`, `/leaderboard/me`.
- Modo mock: la API responde entera sin cadena ni claves.
- Cliente tipado del contrato y lectura de campañas contra el nodo, con caché.
- Relevo de transacciones: envía el claim y paga el gas.
- Subgraph completo — esquema, ABIs, manifiesto y mappings — desplegado en
  Studio. Toda lectura de historial de la API va contra GraphQL.

### Edmer
- `generate.py`: comercios y vecinos sobre el Lower East Side
  (40.7220 / −73.9870), visitas etiquetadas con cuatro patrones de fraude
  inyectados y proporción de fraude al 8%.
- `train.py`: regresión logística y árbol de gradiente contra una línea base
  trivial, con F1 macro y recall de la clase fraude.
- `events.py`: esquema de evento canónico congelado. El pipeline de rasgos
  consume el esquema, no el CSV.

### David
- Sin trabajo en el repositorio.

---

## Día 5 — martes 8 de septiembre
### World ID y el oráculo de fraude en cadena

Sesión de feedback con mentores, 14:00 a 16:00 ET.

**Sebastián**
- Integrar World Selfie Check con la Sandbox App. El `nullifierHash` queda atado
  a la billetera de Privy. Hoy `VisitRegistry.claim` tiene la verificación como
  `TODO`: acepta el nullifier sin comprobarlo contra el router de World.
- Flujo por riesgo, no verificación plana: Selfie Check habilita recompensas
  chicas; para campañas de recompensa alta, exigir Orb u Official ID.
- Revalidación a los 90 días — la verificación de Selfie Check caduca.
- `FraudOracle`: implementar `commitEpoch(bytes32 root, uint64 epoch)` **con
  control de acceso**, y `verifyScore(address, uint16, bytes32[] proof)`. Hoy los
  dos son `revert("not implemented")`. Sin control de acceso, cualquiera puede
  publicar una raíz y se cae el argumento de auditoría entero.
- Confirmar el formato de la hoja del árbol, que es un contrato con la API:

```
leaf = keccak256(keccak256(abi.encode(address wallet, uint16 score)))
node = keccak256(a + b), con el par ordenado
```

  El puntaje viaja en basis points, 0 a 10.000, porque `verifyScore` toma un
  `uint16`. Encaja con `MerkleProof.verify` de OpenZeppelin sin tocar nada.

**Lucio**
- ✅ Ranking con puntos, semana y zona. `GET /leaderboard`, `GET /leaderboard/me`.
- ✅ Árbol de Merkle sobre pares (billetera, puntaje).
- ✅ Servicio de épocas y endpoint de la prueba: `GET /epochs/current`,
  `GET /epochs/{n}`, `GET /epochs/{n}/proof`.
- Publicar la raíz en cadena, en cuanto `commitEpoch` exista.
- Endpoint del Sybil Score de World — espera el permiso de World.

**Edmer**
- **Cerrar el requisito duro del día 4: la inferencia contra el subgraph.**
  `load_events_from_subgraph()` es hoy un stub. The Graph exige textual
  «consumir datos en vivo, no conjuntos simulados ni locales» — el CSV sirve
  para entrenar, la inferencia de la demo corre contra el subgraph o quedamos
  fuera del premio. La URL ya está arriba y responde.
- Rasgos que solo son calculables con el grafo indexado: entropía de comercios
  por billetera y concentración temporal por campaña. Hoy están los cuatro
  rasgos del día 2, con grado de co-visita entre ellos.
- Reentrenar y medir la mejora respecto de la línea base, y commitear la tabla.
- Reemplazar `wallet_score()` en `api/routers/score.py` — devuelve un float de 0
  a 1 y nada más; la API lo convierte a basis points y lo mete en el árbol.
- Sumar el Sybil Score de World como rasgo, cuando llegue el permiso.
- Definir el umbral con la curva de precisión-recall, no a ojo.

**David**
- Todo el trabajo de los días 1 a 4, que sigue sin empezar: scaffold de Next.js
  con TypeScript y Tailwind, login de Privy por correo y por teléfono, alta de
  campaña, barra de búsqueda con selector de radio, resultados sobre mapa,
  escáner de QR, pantalla del comercio que genera el QR firmado rotando cada 30
  segundos, y panel del comercio leyendo del subgraph.
- Flujo de verificación de World con estados de pendiente, verificado y
  rechazado.
- Pantallas de ranking: exploradores y comercios más visitados.

**Hito de cierre.** Un vecino sin verificar no puede cobrar, demostrable en
testnet. Raíz de Merkle publicada con al menos tres épocas. Una prueba de Merkle
verificada en cadena desde el panel.

---

## Día 6 — miércoles 9 de septiembre
### Endurecer: romperlo antes de que lo rompa un juez

**Sebastián**
- Límite de tasa por nullifier y por campaña. Pausa de emergencia para el dueño
  de la campaña.
- Test de que un QR fotografiado y usado dos minutos después revierte.

**Lucio**
- Límite de tasa en la API, monitoreo y alertas.
- Registro estructurado de cada reclamo rechazado y por qué.

**Edmer**
- Simular tres ataques contra el sistema completo y medir la detección: granja
  de treinta billeteras verificadas, comercio que se auto-visita, colusión entre
  dos comercios vecinos.
- Documentar la tasa de detección de cada uno en una tabla.

**David**
- Billeteras de **organización** de Privy para el comercio, no personales. Es
  requisito textual del premio B2B.
- Política de transferencia: el saldo de la campaña solo sale hacia recompensas
  de visita, con tope diario. Cumple el requisito de «al menos un control de
  Privy» siendo además la regla de negocio del producto.
- Un solo «Mi panel» que cambia según el rol, con la columna de estado —pagada,
  retenida, con el puntaje.
- Errores visibles con salida: QR vencido, fuera de radio, ya cobrado hoy,
  verificación pendiente.
- Responsive real: la app del vecino se usa en la calle, con una mano.

**Hito de cierre.** Test de Foundry que prueba que un QR reutilizado revierte.
Tabla de tres ataques con su tasa de detección. App usable en teléfono.

---

## Día 7 — jueves 10 de septiembre
### Despliegue público y datos de demostración

Segunda sesión de feedback, 09:00 a 11:00 ET. **Project Check-in #2, 23:59 ET.**

**Lucio**
- Desplegar la API en producción con dominio y HTTPS. Variables de entorno fuera
  del repositorio. Hoy hay `Dockerfile` y `docker-compose.yml` pero ningún
  destino elegido.
- Dejar el trabajo por época corriendo automáticamente y monitoreado.
- README con las direcciones de los tres contratos, la URL del subgraph y cómo
  levantarlo todo en local.

**Sebastián**
- Sembrar tres campañas de demostración con comercios reconocibles y saldo
  suficiente para que un juez pruebe sin agotarlas. **Hoy la cadena está vacía:
  nadie llamó a `createCampaign`, y sin eso no hay demo, el subgraph no indexa y
  The Graph no ve datos en vivo.**
- Verificar los tres contratos en el explorador y enlazarlos desde el README.

**Edmer**
- Escribir los documentos de feedback que exigen los premios. `the-graph.md` ya
  tiene lo que costó y lo que funcionó del subgraph, y espera los números del
  modelo base contra el modelo con rasgos de grafo. `world.md` tiene la parte de
  backend. Faltan `privy.md` entero y las secciones de SDK y flujo de
  verificación de World.

**David**
- Desplegar el frontend en Vercel con dominio propio.
- Modo demostración: un botón que simula estar en el local, para que un juez en
  otro país complete el recorrido sin viajar a Manhattan.
- Las tres capturas y la imagen de portada del envío.

**Hito de cierre.** URL pública probada desde un dispositivo que nunca tocó el
proyecto. Tres campañas sembradas con saldo. Documentos de feedback commiteados.

---

## Día 8 — viernes 11 de septiembre
### El video y el borrador de envío

**Los cuatro**
- Guion de 3 minutos 30, cronometrado: 25 segundos de problema, 2 minutos de
  demostración en vivo del recorrido completo, 40 segundos de arquitectura con
  el puntaje en cadena, 25 segundos de las tres integraciones.
- Grabar en 1080p, voz clara, **sin música y sin acelerar**. Entre 2 y 4
  minutos: el sistema verifica el archivo y lo rechaza si no cumple.
- Subir y esperar las marcas verdes de verificación.

**Lucio y Edmer**
- README principal: qué es, cómo funciona, métricas medidas y la sección de
  atribución de IA.

**Sebastián y David**
- Descripción larga del envío, con todo el detalle.
- Las tres aplicaciones a premios, con el archivo, la línea y la función exacta
  de cada integración.

**Hito de cierre.** Video subido y verificado. Envío guardado con las tres
aplicaciones cargadas. El proyecto ya está enviado; lo que queda es mejorarlo.

---

## Día 9 — sábado 12 de septiembre
### Margen, pulido y reenvío

Ningún desarrollo nuevo. Hoy solo se arregla lo roto y se pule lo que ya está.

**Los cuatro**
- Recorrer el flujo completo tres veces desde tres dispositivos distintos, uno
  en una red que nunca lo probó.
- Verificar que el repositorio siga público y el despliegue en pie.
- Ensayar las respuestas a las cinco preguntas probables del jurado, con el
  número a mano.

**Sebastián y Lucio**
- Que las direcciones del README coincidan con las desplegadas. Subgraph
  sincronizado y sin errores de indexación.

**Edmer**
- Que las cifras del README coincidan con la última corrida. Una métrica que no
  se puede reproducir es peor que no tenerla.

**David**
- Última pasada de interfaz: nada desalineado, nada roto en teléfono.

**Hito de cierre.** Proyecto reenviado con la versión final, 20 horas antes del
cierre.

---

## Lo que está abierto

### Fusionar a `main` — de los cuatro
`main` tiene un solo archivo. Es lo que ve cualquiera que abra el repositorio y
lo que mira el chequeo automático de ETHGlobal. Tres ramas con 70 commits entre
las tres están fuera. **Cuanto más se demora, más cara sale la fusión.**

### Dónde viven el nombre del comercio y qué vende — decisión pendiente
La cadena guarda geohash, recompensa, tope y radio: no el nombre ni el texto
libre de lo que el comercio vende. Ese texto es lo que hace funcionar la
búsqueda, que es la puerta de entrada del producto y la primera jugada de la
demo. Contra la cadena, `/search` no tiene sobre qué buscar. Propuesta: IPFS, con
el hash dentro de `CampaignCreated` — es una decisión con costo en el contrato.

### Una wallet de relevo con ETH de prueba — Lucio
El relevo está escrito y testeado contra un RPC simulado, pero nunca envió una
transacción real. `RELAY_PRIVATE_KEY` está vacío.

### Esperando a World
El permiso para el Sybil Score sigue sin respuesta. Bloquea el rasgo de Edmer y
el endpoint de Lucio, no el resto de la integración.

---

## Requisitos duros, con dueño y día

### ETHGlobal — descalifica el proyecto entero

| Requisito | Quién | Día | Si falta |
|---|---|---|---|
| Repositorio público durante todo el evento | Sebastián | ya | Descalificación |
| Historial de commits real, incremental | Los cuatro | todos | Filtro ronda 1 |
| Nada de código anterior al 4 de septiembre | Los cuatro | ya | Descalificación |
| Desplegado y usable sin nosotros presentes | Lucio + David | 7 | No hay finalista |
| Video de 2–4 min, 720p, sin música, sin acelerar | Los cuatro | 8 | Rechazo automático |
| Enviar al menos una vez antes del domingo 12:00 ET | Uno solo | 8 | Sin premios |
| **Project Check-in #1 — lunes 7, 23:59 ET** | Uno solo | **hoy** | Se pierde el depósito |
| Project Check-in #2 — jueves 10, 23:59 ET | Uno solo | 7 | Se pierde el depósito |
| Sección de atribución de IA en el README | Lucio + Edmer | 8 | Riesgo de descalificación |
| Los cuatro en la ronda 2: lunes 14, 12:00–14:00 ET | Los cuatro | — | Descalificación automática |

### World — 3.500 USD

| Requisito | Quién | Día |
|---|---|---|
| Selfie Check integrado y funcionando de punta a punta | Sebastián | 5 |
| Usado como señal de riesgo, no como simple login | Sebastián | 5 |
| Sybil Score como rasgo del modelo | Edmer | 5 |
| Revalidación a los 90 días contemplada | Sebastián | 5 |
| Documento de feedback — vale el 25% del premio | Los cuatro | 1 a 7 |

### Privy — 5.000 USD

| Requisito | Quién | Día |
|---|---|---|
| Privy como componente central, no accesorio | David | 1 a 5 |
| Al menos una billetera de Privy funcionando | David | 1 |
| Billeteras de organización para el comercio | David | 6 |
| Al menos un control: política de transferencia con tope | David | 6 |
| Una transacción financiera real completada | Sebastián | 3 |
| Explicar cómo Privy mejora el producto | Los cuatro | 8 |

### The Graph — 10.000 USD

| Requisito | Quién | Día |
|---|---|---|
| Subgraph desplegado y consultable públicamente | Lucio | ✅ 4 |
| Datos en vivo: la inferencia corre contra el subgraph | Edmer | 5 |
| Rasgos de grafo imposibles sin índice, con la mejora medida | Edmer | 5 |
| Devolver el razonamiento, no solo el resultado en crudo | Edmer | 5 |
| Ranking por visitas, como consulta al subgraph | Lucio | ✅ 5 |

---

## El orden de sacrificio

Si algo se cae, está escrito de antemano:

**Bucle de pago → subgraph y modelo → ranking → trivia.**

Si el bucle de pago falla en la demostración, nada de lo demás importa. Un jurado
perdona una función que falta; no perdona una demo que no funciona.

**Nunca se sacrifican los documentos de feedback:** valen el 25% del premio de
World y se escriben mientras se integra, no ocupan un bloque de tiempo propio.
