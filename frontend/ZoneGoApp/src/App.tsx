import { useState } from 'react'
import { usePrivy } from '@privy-io/react-auth'
import { useRole } from './context/RoleContext'
import { Onboarding } from './screens/Onboarding'
import { Search } from './screens/Search'
import { MyQr } from './screens/MyQr'
import { ScanQr } from './screens/ScanQr'
import { MerchantPanel } from './screens/MerchantPanel'
import { IdentityCheck } from './screens/IdentityCheck'
import { Leaderboard } from './screens/Leaderboard'
import type { SearchHit, WorldAttestation } from './lib/api'

function RoleFallback() {
  const { setRole } = useRole()
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="text-gray-600">We couldn't remember your role. How are you signing in?</p>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => setRole('comercio')}
          className="rounded-lg bg-black px-6 py-3 font-medium text-white"
        >
          I'm a merchant
        </button>
        <button
          type="button"
          onClick={() => setRole('vecino')}
          className="rounded-lg border border-gray-300 px-6 py-3 font-medium text-gray-900"
        >
          I'm a neighbor
        </button>
      </div>
    </div>
  )
}

function App() {
  const { ready, authenticated, user } = usePrivy()
  const { role } = useRole()
  const [attestation, setAttestation] = useState<WorldAttestation | null>(null)
  const [selectedHit, setSelectedHit] = useState<SearchHit | null>(null)
  const [merchantView, setMerchantView] = useState<'panel' | 'scan'>('panel')
  const [showLeaderboard, setShowLeaderboard] = useState(false)

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    )
  }

  if (!authenticated) {
    return <Onboarding />
  }

  if (!role) {
    return <RoleFallback />
  }

  // Merchant side.
  if (role === 'comercio') {
    if (merchantView === 'scan') {
      return <ScanQr />
    }
    return (
      <MerchantPanel
        merchantAddress={import.meta.env.VITE_DEV_MERCHANT_ADDRESS || user?.wallet?.address || ''}
        onGoToScan={() => setMerchantView('scan')}
      />
    )
  }

  // Neighbor side.
  const visitorAddress = user?.wallet?.address
  if (!visitorAddress) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6 text-center">
        <p className="text-red-600">
          No wallet found for your account yet. Try signing out and back in.
        </p>
      </div>
    )
  }

  if (!attestation) {
    return <IdentityCheck visitorAddress={visitorAddress} onVerified={setAttestation} />
  }

  if (showLeaderboard) {
    return (
      <div>
        <button
          type="button"
          onClick={() => setShowLeaderboard(false)}
          className="px-4 pt-4 text-sm text-gray-600"
        >
          &larr; Back
        </button>
        <Leaderboard myAddress={visitorAddress} />
      </div>
    )
  }

  if (selectedHit) {
    return (
      <MyQr
        visitorAddress={visitorAddress}
        campaign={selectedHit.campaign}
        attestation={attestation}
        onBack={() => setSelectedHit(null)}
      />
    )
  }

  return (
    <div>
      <div className="flex justify-end px-4 pt-4">
        <button
          type="button"
          onClick={() => setShowLeaderboard(true)}
          className="text-sm text-gray-600 underline"
        >
          Rankings
        </button>
      </div>
      <Search onSelectCampaign={setSelectedHit} />
    </div>
  )
}

export default App