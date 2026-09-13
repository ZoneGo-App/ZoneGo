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

/**
 * createCampaign(uint256,uint256,bytes32,uint256) — selector verified with
 * keccak256 against the real hardcoded seed-campaign calldata:
 * createCampaign(rewardPerVisit=50000, dailyCap=50, geohash="dr5rsked", radius=120)
 * decodes byte-for-byte to that exact calldata, confirming both the
 * selector and the bytes32 (left-aligned, zero-padded on the right)
 * encoding for the geohash argument — unlike uint256, which right-aligns.
 */
function encodeBytes32String(value: string): string {
  const bytes = new TextEncoder().encode(value)
  if (bytes.length > 32) throw new Error('Value too long for bytes32')
  const hex = Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
  return hex.padEnd(64, '0')
}

export function encodeCreateCampaign(
  rewardPerVisit: bigint,
  dailyCap: bigint,
  geohash: string,
  radiusMeters: bigint,
): `0x${string}` {
  return `0x4247c05a${encodeUint(rewardPerVisit)}${encodeUint(dailyCap)}${encodeBytes32String(
    geohash,
  )}${encodeUint(radiusMeters)}` as `0x${string}`
}

/**
 * Standard geohash encoding (the same algorithm events.py's
 * _decode_geohash reverses) — turns a real lat/lon into the 8-character
 * geohash the contract expects, so a merchant's campaign can be anchored
 * to wherever they actually are instead of the hardcoded Delancey Street
 * demo location. Round-trip verified: encoding the real campaign #1
 * coordinates (40.718508, -73.987942) reproduces "dr5rsked" exactly.
 */
export function encodeGeohash(lat: number, lon: number, precision = 8): string {
  const BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'
  let latRange: [number, number] = [-90.0, 90.0]
  let lonRange: [number, number] = [-180.0, 180.0]
  let isEven = true
  let bit = 0
  let ch = 0
  let geohash = ''

  while (geohash.length < precision) {
    if (isEven) {
      const mid = (lonRange[0] + lonRange[1]) / 2
      if (lon > mid) {
        ch |= 1 << (4 - bit)
        lonRange = [mid, lonRange[1]]
      } else {
        lonRange = [lonRange[0], mid]
      }
    } else {
      const mid = (latRange[0] + latRange[1]) / 2
      if (lat > mid) {
        ch |= 1 << (4 - bit)
        latRange = [mid, latRange[1]]
      } else {
        latRange = [latRange[0], mid]
      }
    }
    isEven = !isEven
    if (bit < 4) {
      bit++
    } else {
      geohash += BASE32[ch]
      bit = 0
      ch = 0
    }
  }
  return geohash
}
