ZONEGO
> El comerciante promedio no puede pagar publicidad que cobra por clics. ZONEGO cobra solamente cuando una persona real cruza la puerta de su local — verificada con World ID, liquidada en USDC sobre Base, en el mismo segundo.
---
El problema
Los canales de publicidad tradicionales (redes sociales, volanteo) cobran por atención: un clic, una impresión, un volante repartido. Ninguno garantiza que esa atención se convierta en una persona real entrando al local. El comerciante de barrio paga igual, convierta o no.
La solución
ZONEGO es una red publicitaria donde el comercio solo paga cuando un humano único, verificado, entra físicamente a su local — no antes. El vecino que camina hasta ahí cobra directo a su billetera, sin fricción de onboarding cripto.
Quién	Qué pone	Qué se lleva
Comerciante	USDC por visita verificada	Una persona adentro del local
Vecino	Una caminata	USDC al instante, sin registro ni tarjeta
Protocolo	Infraestructura e indexación	Comisión del protocolo, sin custodiar el presupuesto
Decisión de arquitectura clave
El comercio firma cada visita con EIP-712, y es el vecino quien envía esa firma directo al contrato — el backend nunca tiene autoridad sobre qué visita cuenta como real. Esto es intencional: si el backend pudiera decidir qué visita es válida, todo el sistema de confianza se vendría abajo con un solo punto de falla.
Por qué no se farmea en 20 minutos
Todo esquema de "camina y cobra" muere por fraude. Estas son las puertas que lo evitan, en el orden en que un atacante las intenta:
El ataque	La puerta
Mil cuentas, un solo humano	El pago se liquida contra la verificación de World ID (Selfie Check), no contra la billetera — mil billeteras del mismo humano son un solo cobro
El mismo humano cobrando en loop	El contrato registra la última visita por humano y por tienda, y rechaza antes de que pase el período de espera
Cobrar desde el sillón, sin ir	Se requiere una prueba de presencia en el local al momento del check-in, no solo la ubicación del teléfono
Vaciar el presupuesto de un comercio de golpe	Tope de visitas por hora por campaña, fijado por el propio comerciante al depositar
Puntuación de riesgo poco auditable	El modelo de fraude entrena sobre datos sintéticos con patrones inyectados y publica su puntaje como raíz de Merkle en cadena (FraudOracle), para que sea verificable por cualquiera
Stack e integraciones
Pieza	Rol en ZONEGO
World ID	Prueba de humano único (Selfie Check) — convierte "una billetera" en "una persona"
Privy	Billeteras embebidas para comercio y vecino — onboarding sin frase semilla
The Graph	Subgraph como fuente de datos para el modelo de fraude y el panel de campaña
Base	Liquidación de pagos en USDC
Se evaluó integrar Hedera/x402 pese al premio disponible, pero se descartó porque hubiera obligado a desplegar en una segunda cadena — decisión consciente de simplicidad sobre cobertura de premios.
Qué está vivo y qué está actuado en la demo
Pieza	En esta demo	Qué falta para el sistema real
Buscador y agente	Real	Reemplazar el catálogo local por la consulta al subgraph
Mapa, rutas y distancias	Real	Tile server y coordenadas reales
Regla anti-doble-cobro	Real (lógica en cliente)	Mover la lógica del nullifier al contrato
Prueba de World ID	Actuado	IDKit widget + verificación on-chain con `verifyProof`
Transacción en Base	Actuado	`BarrioCampaign.sol` en Base Sepolia + Smart Wallet con passkeys
Catálogos en IPFS	Actuado	Subida vía Fleek/Storacha con CID guardado en el evento del contrato
Hackathon
Construido para ETHOnline 2026, vía el programa From Scratch. Fecha límite de entrega: domingo 13 de septiembre, 12:00 ET.
Cómo correrlo localmente
> Ajusta esta sección según la estructura real del repo.
```bash
# clonar el repo
git clone <url-del-repo>
cd zonego

# instalar dependencias del frontend
npm install

# variables de entorno necesarias (World ID, Privy, RPC de Base Sepolia, etc.)
cp .env.example .env

# correr en local
npm run dev
```
Los contratos (`BarrioCampaign.sol`, `FraudOracle`) se despliegan en Base Sepolia; revisa la carpeta de contratos para los scripts de deploy.
Licencia
Por definir.
