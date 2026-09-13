export const CAMPAIGN_VAULT_ADDRESS = '0x7b4aaDDe248818bAD121431eAd1a3A865914c419'
export const USDC_ADDRESS = '0x036CbD53842c5426634e7929541eC2318f3dCF7e'
export const BASE_SEPOLIA_CHAIN_ID = 84532

function padHex(hex: string): string {
  return hex.replace(/^0x/i, '').padStart(64, '0')
}

function encodeAddress(address: string): string {
  return padHex(address.toLowerCase())
}

function encodeUint(value: bigint): string {
  return padHex(value.toString(16))
}

/**
 * approve(address,uint256) — selector verified with keccak256, same one
 * already used for the hardcoded seed-campaign calldata.
 */
export function encodeApprove(spender: string, amount: bigint): `0x${string}` {
  return `0x095ea7b3${encodeAddress(spender)}${encodeUint(amount)}` as `0x${string}`
}

/**
 * fund(uint256,uint256) — selector verified with keccak256.
 */
export function encodeFund(campaignId: bigint, amount: bigint): `0x${string}` {
  return `0xa65e2cfd${encodeUint(campaignId)}${encodeUint(amount)}` as `0x${string}`
}

/** Converts a USD amount (e.g. 20 or 12.5) to the micro-USDC integer the contract expects. */
export function usdToMicroUsdc(usd: number): bigint {
  return BigInt(Math.round(usd * 1_000_000))
}