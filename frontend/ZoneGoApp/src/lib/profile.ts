export interface MerchantProfile {
  name: string
  address: string
  description: string
}

export interface VisitorProfile {
  name: string
  nickname: string
}

function merchantKey(wallet: string): string {
  return `zonego_merchant_profile:${wallet.toLowerCase()}`
}

function visitorKey(wallet: string): string {
  return `zonego_visitor_profile:${wallet.toLowerCase()}`
}

export function readMerchantProfile(wallet: string): MerchantProfile | null {
  if (!wallet) return null
  const raw = localStorage.getItem(merchantKey(wallet))
  if (!raw) return null
  try {
    return JSON.parse(raw) as MerchantProfile
  } catch {
    return null
  }
}

export function saveMerchantProfile(wallet: string, profile: MerchantProfile): void {
  localStorage.setItem(merchantKey(wallet), JSON.stringify(profile))
}

export function readVisitorProfile(wallet: string): VisitorProfile | null {
  if (!wallet) return null
  const raw = localStorage.getItem(visitorKey(wallet))
  if (!raw) return null
  try {
    return JSON.parse(raw) as VisitorProfile
  } catch {
    return null
  }
}

export function saveVisitorProfile(wallet: string, profile: VisitorProfile): void {
  localStorage.setItem(visitorKey(wallet), JSON.stringify(profile))
}