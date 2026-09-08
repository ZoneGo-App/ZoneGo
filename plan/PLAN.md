# ZoneGo — Plan de ejecución · 9 días

**ETHOnline 2026 · Vía From Scratch · Base Sepolia · Equipo de cuatro**
Estado al **lunes 7 de septiembre — día 4**. Cierre: **domingo 13, 12:00 ET**.

El hackathon arrancó el viernes 4 de septiembre a las 12:00 ET. Cada día cierra
con un hito verificable: **si no se puede demostrar, el día no está cerrado.**
El ✔ marca lo que ya se puede demostrar hoy.

---

## El producto

El vecino busca algo cerca, camina hasta el local, escanea un QR y cobra. El
comercio paga solo cuando un humano único verificado cruza su puerta, y puede
auditar cada pago contra la cadena sin confiar en nosotros.

**La decisión que sostiene todo:** el comercio firma la visita con EIP-712 desde
su dispositivo, el vecino envía esa firma al contrato, y el contrato la verifica
en cadena. Nuestro servidor paga el gas por comodidad, no por autoridad.

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
`schema/events.md` y nadie lo cambia sin acuerdo de los cuatro.

---

## Lo que está en pie hoy

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

### Ramas

| Rama | Commits sobre `main` | Contenido |
|---|---|---|
| `feat/api-base` | 57 | API con 12 endpoints, 164 tests, subgraph |
| `feat/contracts-skeleton` | 11 | Tres contratos, desplegados, 4 tests |
| `feat/data-scientist` | 2 | Generador, esquema de eventos, entrenamiento |
| `main` | — | **Un solo archivo: `README.md`** |

---

# DÍA 1 — viernes 4 de septiembre
## Cimientos, contrato de datos y decisión de cadena

**Foco.** Congelar el esquema de eventos para desbloquear a los cuatro en
paralelo, y dejar el repositorio con historial real desde la primera hora.

### Sebastián — contratos y Web3
- ✔ Organización de GitHub y repositorio público con licencia MIT, `.gitignore`
  y README inicial. Enlazado en el panel de ETHGlobal.
- ✔ Foundry en `/contracts`. Interfaces y eventos de los tres contratos.
- ✔ `struct` EIP-712 de la visita y su typehash — el contrato entre el QR y la
  cadena.
- ✔ La cadena es **Base Sepolia**: World ID Router en
  `0x42FF98C4E85212a5D31358ACbFe76a621b50fC02`, The Graph la indexa como
  `base-sepolia` (chainId 84532), Privy es agnóstico.

### Lucio — servicios e infraestructura
- ✔ CI en GitHub Actions: los tests corren en cada push y cada PR.
- ✔ Esqueleto de FastAPI en `/api` con `/health`, Pydantic y `docker-compose`.
- ✔ Servidor simulado con el esquema congelado, para que David no espere.

### Edmer — ciencia de datos
- ✔ `generate.py`: comercios con horario y coordenadas reales del Lower East
  Side (40,7220 / −73,9870), vecinos, y visitas etiquetadas.
- ✔ Cuatro patrones de fraude inyectados: viaje imposible, co-visita
  sistemática, ráfaga fuera de horario, reclamo repetido bajo distinto nullifier.
- ✔ Proporción de fraude al 8%, desbalanceada a propósito.

### David — frontend y producto
- ✗ Scaffold de Next.js 14 con TypeScript y Tailwind.
- ✗ `@privy-io/react-auth` con login por correo y por teléfono, mostrando la
  dirección de la billetera embebida.

**Hito de cierre.** Repositorio público enlazado con commits de cuatro autores.
Cadena decidida. `forge build` compila. CI en verde. Login de Privy funcionando.
`docker compose up` levanta la API. 20.000 visitas etiquetadas en CSV.

---

# DÍA 2 — sábado 5 de septiembre
## Campañas en cadena y línea base del modelo

**Foco.** Que un comercio pueda crear y financiar una campaña en testnet, y tener
un número contra el cual medir el modelo el resto de la semana.

### Sebastián — contratos y Web3
- ✔ `CampaignVault.sol`: `createCampaign(rewardPerVisit, dailyCap, geohash,
  radius)`, `fund()` con USDC de prueba, `withdraw()` del remanente.
- ✔ Tests de los caminos de error: financiar campaña inexistente, retirar sin ser
  dueño, superar el tope diario.
- ✔ Desplegar en testnet.

### Lucio — servicios e infraestructura
- ✔ Lectura de campañas contra el nodo, con caché. Cliente tipado del contrato.
- ✔ `POST /qr/sign`: el servidor arma el payload EIP-712 **pero no firma** —
  firma el comercio con su billetera.

### Edmer — ciencia de datos
- ✔ Rasgos v1: tiempo desde la visita anterior del mismo nullifier, velocidad
  implícita entre locales, desvío del horario modal, grado de co-visita.
- ✔ Regresión logística balanceada y árbol de gradiente, contra la línea base
  trivial.
- ✔ F1 macro y recall de la clase fraude. **El recall es la métrica que importa:**
  dejar pasar fraude cuesta dinero del comercio.

### David — frontend y producto
- ✗ Pantalla de creación de campaña: rubro, recompensa, presupuesto, tope diario
  y radio sobre un mapa.
- ✗ Conectar al contrato con `wagmi` + `viem`, firmando con la billetera de Privy.

**Hito de cierre.** Campaña creada y financiada con USDC de prueba, visible en el
explorador con su hash. Tabla comparativa de dos modelos con F1 macro.

---

# DÍA 3 — domingo 6 de septiembre
## El bucle completo, y el backend fuera de la ruta de confianza

**Foco.** Que una visita termine en transferencia real de USDC en testnet, con el
contrato verificando la firma del comercio. Es el día más importante de los nueve.

### Sebastián — contratos y Web3
- ✔ `VisitRegistry.claim(...)`: verifica **en cadena** la firma EIP-712 del
  comercio, la vigencia, el nullifier y el tope diario. Transfiere y emite.
- ✔ Nonce de un solo uso por comercio, registrado en cadena.
- ✔ **La curva decreciente en el contrato**: 1ª visita 100%, 2ª 50%, 3ª 25%,
  4ª 0, por semana. **La calcula el contrato, no el servidor** — si la decide el
  backend, volvemos a ser autoridad y se cae la respuesta al jurado.

### Lucio — servicios e infraestructura
- ✔ Relevo de transacciones, documentado como opcional: el vecino puede enviar la
  firma él mismo.
- ✔ `GET /search?q=&lat=&lon=&radius=` — la puerta de entrada del producto.
  Filtro por rubro y palabra sobre lo que el comercio declaró que vende, más
  distancia. Sin modelo. Radio de 1, 5 o 10 km.
- ✔ `POST /score` devolviendo puntaje y los tres rasgos que más pesaron.

### Edmer — ciencia de datos
- ✔ Arreglar el generador: geografía a Nueva York (sigma 0,008), un nullifier
  estable por billetera, y que el viaje imposible mueva al visitante.
- ✔ Reescribir el pipeline de rasgos para que consuma **el esquema del evento**,
  no el CSV.
- Clasificador de rubro desde la descripción libre — TF-IDF y regresión logística.

### David — frontend y producto
- ✗ Barra de búsqueda y selector de radio. Es la primera pantalla de la app.
- ✗ Resultados sobre mapa de Google embebido, cada comercio mostrando cuánto
  paga hoy.
- ✗ Autocompletado de Places en el alta del comercio, guardando el `place_id`.
- ✗ Escáner de QR con `html5-qrcode` y confirmación de cobro.
- ✗ Pantalla del comercio que genera el QR firmado, **regenerándolo cada 30
  segundos**. La firma vale 90, para que un escaneo lento no falle.

**Hito de cierre.** Bucle completo en testnet: buscar «sneakers», ver comercios
en el radio, generar QR firmado, escanear, reclamar y recibir USDC. El hash de
esa primera transacción va al README.

---

# DÍA 4 — lunes 7 de septiembre · HOY
## El subgraph: The Graph como fuente de verdad

**Foco.** Sacar todas las consultas de historial de la base propia y ponerlas
contra el subgraph. **Project Check-in #1, 23:59 ET.**

### Lucio — servicios e infraestructura
- ✔ `schema.graphql` con Campaign, Visit, Merchant y Visitor y relaciones
  derivadas. Diez entidades.
- ✔ Mappings en AssemblyScript y **despliegue en Subgraph Studio**. Entidades
  agregadas por hora y por comercio.
- ✔ Toda lectura de historial de la API va contra GraphQL.

### Sebastián — contratos y Web3
- ✔ `CampaignCreated` emite geohash y radius. **Última ventana para tocar el
  esquema.**
- ✔ Redesplegar los tres contratos, con `FraudOracle` en `DeployAll.s.sol`.
- ✔ Empezar `FraudOracle.sol`: firmas de `commitEpoch` y `verifyScore`.

### Edmer — ciencia de datos
- ✗ **[REQUISITO DURO]** Cliente GraphQL contra el subgraph. Hoy
  `load_events_from_subgraph()` es un stub. **La URL ya está arriba y responde.**
- ✗ Rasgos que *solo* son calculables con el grafo indexado: entropía de
  comercios visitados y concentración temporal por campaña.
- ✗ Reentrenar y medir la mejora respecto de la línea base del día 2, y
  commitear la tabla.
- Devolver siempre los tres rasgos que más pesaron.

### David — frontend y producto
- ✗ Panel del comercio leyendo del subgraph: visitas por hora, costo por visita
  real, presupuesto restante.
- ✗ Estados vacíos y de carga en todas las vistas.

> **El requisito que descalifica un premio de 10.000.** The Graph exige textual
> *«consumir datos en vivo, no conjuntos simulados ni locales»*. El CSV sirve
> para entrenar; la inferencia de la demo corre contra el subgraph o quedamos
> fuera del premio.

**Hito de cierre.** Subgraph desplegado y consultable por URL pública. El panel
se alimenta solo de GraphQL. Métrica del modelo antes y después de los rasgos de
grafo.

---

# DÍA 5 — martes 8 de septiembre
## World ID y el oráculo de fraude en cadena

**Foco.** Cerrar el agujero de Sybil y llevar la salida del modelo a la cadena.
Sesión de feedback con mentores, 14:00 a 16:00 ET.

### Sebastián — contratos y Web3
- Integrar **World Selfie Check** con la Sandbox App. El `nullifierHash` queda
  atado a la billetera de Privy. Hoy `VisitRegistry.claim` tiene la verificación
  como `TODO`: acepta el nullifier sin comprobarlo contra el router de World.
- **Flujo por riesgo, no verificación plana:** Selfie Check habilita recompensas
  chicas; para recompensa alta, exigir Orb u Official ID.
- **Revalidación a los 90 días** — la verificación de Selfie Check caduca.
- Terminar `FraudOracle`: `commitEpoch(bytes32 root, uint64 epoch)` **con control
  de acceso**, y `verifyScore(address, uint16, bytes32[] proof)`. Hoy los dos son
  `revert("not implemented")`.
- Confirmar el formato de la hoja del árbol:

```
leaf = keccak256(keccak256(abi.encode(address wallet, uint16 score)))
node = keccak256(a + b), con el par ordenado
```

  El puntaje va en basis points, 0 a 10.000 (0,7213 → 7213), porque
  `verifyScore` toma un `uint16`. Encaja con `MerkleProof.verify` de OpenZeppelin
  sin tocar nada. Sin control de acceso en `commitEpoch`, cualquiera puede
  publicar una raíz y se cae el argumento de auditoría entero.

### Lucio — servicios e infraestructura
- ✔ El ranking, como consulta al subgraph. `GET /leaderboard`: 5 puntos por
  visita, 10 si el comercio es nuevo, 0 el mismo local el mismo día. Semanal y de
  por vida. **Los puntos los cuenta la cadena, no nuestra base.**
- ✔ Competencia por zona: los primeros seis caracteres del geohash que el
  comercio ya firma, unas seis cuadras. Sin datos de mapas ni API.
- ✔ Panel personal. `GET /leaderboard/me`: puntos propios, cuántos juegan en esa
  zona, y cuántos faltan para pasar al de arriba.
- ✔ Árbol de Merkle sobre pares (billetera, puntaje).
- ✔ Servicio de época y endpoint de la prueba: `GET /epochs/current`,
  `GET /epochs/{n}`, `GET /epochs/{n}/proof`.
- Publicar la raíz en cadena cada hora, en cuanto `commitEpoch` exista.
- Endpoint del **Sybil Score** de World — espera el permiso de World.

### Edmer — ciencia de datos
- Cerrar lo del día 4 antes que nada: la inferencia contra el subgraph y los
  rasgos de grafo.
- Reemplazar `wallet_score()` en `api/routers/score.py`: devuelve un float de 0 a
  1 y nada más — la API lo convierte a basis points y lo mete en el árbol.
- Sumar el **Sybil Score de World** como rasgo, combinado con los rasgos de
  co-visita del subgraph.
- Definir el umbral con la curva de precisión-recall, no a ojo.
- Preparar la respuesta a «¿qué pasa si el modelo se equivoca?»: la retención es
  reversible y el vecino puede apelar.

### David — frontend y producto
- **Todo lo pendiente de los días 1 a 4** — es la ruta crítica del proyecto.
- Flujo de verificación de World con estados de pendiente, verificado y rechazado.
- Pantalla de ranking — Zone Explorers. Tabla semanal, tu puesto, y el histórico
  de comercios descubiertos.
- Segunda tabla: comercios más visitados del barrio. Sale del mismo subgraph.
- Panel de fraude del comercio: visitas retenidas, puntaje, y los rasgos que lo
  explican.
- Presentar en la sesión de feedback de las 14:00 ET.

**Hito de cierre.** Un vecino sin verificar no puede cobrar, demostrable en
testnet. Raíz de Merkle publicada con al menos tres épocas. Una prueba de Merkle
verificada en cadena desde el panel.

---

# DÍA 6 — miércoles 9 de septiembre
## Endurecer: romperlo antes de que lo rompa un juez

**Foco.** Atacar el sistema a propósito y medir qué aguanta. Es el día que separa
un prototipo de un producto.

### Sebastián — contratos y Web3
- Protección contra repetición: un QR fotografiado y usado dos minutos después
  debe revertir. **Escribir el test que lo demuestra.**
- Límite de tasa por nullifier y por campaña. Pausa de emergencia para el dueño
  de la campaña.

### Lucio — servicios e infraestructura
- Límite de tasa en la API, monitoreo y alertas.
- Registro estructurado de cada reclamo rechazado y por qué.

### Edmer — ciencia de datos
- Simular tres ataques y medir la detección: granja de treinta billeteras
  verificadas, comercio que se auto-visita, colusión entre dos comercios vecinos.
- Documentar la tasa de detección de cada uno en una tabla.

### David — frontend y producto
- **Billeteras de organización** de Privy para el comercio, no personales.
  Requisito textual del premio B2B.
- **Política de transferencia:** el saldo de la campaña solo sale hacia
  recompensas de visita, con tope diario.
- Fusionar alta de campaña y panel en una sola vista «Mi panel», que cambia según
  el rol, con la columna de estado: pagada, retenida, con el puntaje.
- Errores visibles con salida: QR vencido, fuera de radio, ya cobrado hoy,
  verificación pendiente.
- Responsive real: la app se usa en la calle, en un teléfono, con una mano.

**Hito de cierre.** Test de Foundry que prueba que un QR reutilizado revierte.
Tabla de tres ataques con su tasa de detección. App usable en teléfono.

---

# DÍA 7 — jueves 10 de septiembre
## Despliegue público y datos de demostración

**Foco.** Que cualquiera con el enlace pueda usar ZoneGo sin nosotros presentes.
Requisito duro para ser finalista. Segunda sesión de feedback, 09:00 a 11:00 ET.
**Project Check-in #2, 23:59 ET.**

### Lucio — servicios e infraestructura
- Desplegar la API en producción con dominio y HTTPS. Variables de entorno fuera
  del repositorio. Hoy hay `Dockerfile` y `docker-compose.yml` pero **ningún
  destino elegido**.
- Dejar el trabajo por época corriendo automáticamente y monitoreado.
- README con las direcciones de los tres contratos, la URL del subgraph y cómo
  levantarlo todo en local.

### Sebastián — contratos y Web3
- Sembrar tres campañas de demostración con comercios reconocibles y saldo
  suficiente para que un juez pruebe sin agotarlas.
- Verificar los tres contratos en el explorador y enlazarlos desde el README.

> **Y esto no puede esperar al jueves.** La cadena está vacía: nadie llamó a
> `createCampaign`. Sin una campaña real no hay demo, el subgraph no tiene qué
> indexar, y The Graph no ve datos en vivo. Una sola llamada destraba las tres.

### Edmer — ciencia de datos
- Escribir los documentos de feedback que exigen los premios. `the-graph.md` ya
  tiene lo que costó y lo que funcionó del subgraph, y espera los números del
  modelo base contra el modelo con rasgos de grafo. `world.md` tiene la parte de
  backend. Faltan `privy.md` entero y las secciones de SDK y flujo de
  verificación de World.

### David — frontend y producto
- Desplegar el frontend en Vercel con dominio propio.
- **Modo demostración:** un botón que simula estar en el local, para que un juez
  en otro país complete el recorrido sin viajar a Manhattan.
- Las tres capturas y la imagen de portada del envío.

**Hito de cierre.** URL pública probada desde un dispositivo que nunca tocó el
proyecto. Tres campañas sembradas con saldo. Documentos de feedback commiteados.

---

# DÍA 8 — viernes 11 de septiembre
## El video y el borrador de envío

**Foco.** El video es el filtro de la ronda 1 y lo que ven los patrocinadores. Se
hace hoy, con dos días de margen.

### Todo el equipo — los cuatro
- Guion de **3 minutos 30, cronometrado**: 25 s de problema, 2 min de
  demostración en vivo del recorrido completo, 40 s de arquitectura con el
  puntaje en cadena, 25 s de las tres integraciones.
- Grabar en 1080p, voz clara, **sin música y sin acelerar**. Entre 2 y 4 minutos,
  corte duro: el sistema verifica el archivo y lo rechaza si no cumple.
- Subir y esperar las marcas verdes de verificación.

### Lucio y Edmer — servicios + datos
- README principal: qué es, cómo funciona, métricas medidas, y la sección de
  atribución de IA que ETHGlobal pide explícitamente.
- Copiar los documentos de planificación a `/plan`.

### Sebastián y David — cadena + frontend
- Descripción larga del envío. Cuanto más detalle, más fácil es evaluarlo.
- Las tres aplicaciones a premios, con el archivo, la línea y la función exacta
  de cada integración.

**Hito de cierre.** Video subido y verificado. Envío guardado con las tres
aplicaciones cargadas. El proyecto ya está enviado; lo que queda es mejorarlo.

---

# DÍA 9 — sábado 12 de septiembre
## Margen, pulido y reenvío

**Foco.** Ningún desarrollo nuevo. Hoy solo se arregla lo roto y se pule lo que ya
está.

### Todo el equipo — los cuatro
- Recorrer el flujo completo tres veces desde tres dispositivos distintos, uno en
  una red que nunca lo probó.
- Verificar que el repositorio siga público y el despliegue en pie.
- Ensayar las respuestas a las cinco preguntas probables del jurado, con el
  número a mano.

### Sebastián y Lucio — cadena + infra
- Que las direcciones del README coincidan con las desplegadas. Subgraph
  sincronizado y sin errores de indexación.

### Edmer — ciencia de datos
- Que las cifras del README coincidan con la última corrida. **Una métrica que no
  se puede reproducir es peor que no tenerla.**

### David — frontend y producto
- Última pasada de interfaz: nada desalineado, nada a medio traducir, nada roto
  en teléfono.

**Hito de cierre.** Proyecto reenviado con la versión final, 20 horas antes del
cierre. Los cuatro con el enlace público probado desde su teléfono.

---

## Lo que está abierto

### Fusionar a `main` — de los cuatro
`main` tiene un solo archivo. Es lo que ve cualquiera que abra el repositorio y
lo que mira el chequeo automático de ETHGlobal. Tres ramas con 70 commits entre
las tres están fuera. Cuanto más se demora, más cara sale la fusión.

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
| Subgraph desplegado y consultable públicamente | Lucio | ✔ 4 |
| Datos en vivo: la inferencia corre contra el subgraph | Edmer | 4 |
| Rasgos de grafo imposibles sin índice, con la mejora medida | Edmer | 4 |
| Devolver el razonamiento, no solo el resultado en crudo | Edmer | 4 |
| Ranking por visitas, como consulta al subgraph | Lucio | ✔ 5 |

---

## El orden de sacrificio

Si algo se cae, está escrito de antemano:

**Bucle de pago → subgraph y modelo → ranking → trivia.**

Si el bucle de pago falla en la demostración, nada de lo demás importa. Un jurado
perdona una función que falta; no perdona una demo que no funciona.

**Nunca se sacrifican los documentos de feedback:** valen el 25% del premio de
World y se escriben mientras se integra, no ocupan un bloque de tiempo propio.
