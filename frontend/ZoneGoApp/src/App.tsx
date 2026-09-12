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
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg px-6 text-center">
      <p className="text-ink-muted">We couldn't remember your role. How are you signing in?</p>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => setRole('comercio')}
          className="rounded-full bg-brand px-6 py-3 font-medium text-white"
        >
          I'm a merchant
        </button>
        <button
          type="button"
          onClick={() => setRole('vecino')}
          className="rounded-full border border-border px-6 py-3 font-medium text-ink"
        >
          I'm a neighbor
        </button>
      </div>
    </div>
  )
}

function LogoutBar() {
  const { logout } = usePrivy()
  const { setRole } = useRole()

  async function handleLogout() {
    setRole(null)
    await logout()
  }

  return (
    <div className="flex justify-end bg-bg px-4 pt-4">
      <button
        type="button"
        onClick={handleLogout}
        className="text-sm text-ink-muted underline"
      >
        Log out
      </button>
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
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <p className="text-ink-muted">Loading...</p>
      </div>
    )
  }

  if (!authenticated) {
    return <Onboarding />
  }

  let content: React.ReactNode

  if (!role) {
    content = <RoleFallback />
  } else if (role === 'comercio') {
    // Merchant side.
    content =
      merchantView === 'scan' ? (
        <ScanQr />
      ) : (
        <MerchantPanel
          merchantAddress={import.meta.env.VITE_DEV_MERCHANT_ADDRESS || user?.wallet?.address || ''}
          onGoToScan={() => setMerchantView('scan')}
        />
      )
  } else {
    // Neighbor side.
    const visitorAddress = user?.wallet?.address
    if (!visitorAddress) {
      content = (
        <div className="flex min-h-screen items-center justify-center bg-bg px-6 text-center">
          <p className="text-red-600">
            No wallet found for your account yet. Try signing out and back in.
          </p>
        </div>
      )
    } else if (!attestation) {
      content = <IdentityCheck visitorAddress={visitorAddress} onVerified={setAttestation} />
    } else if (showLeaderboard) {
      content = (
        <div className="bg-bg">
          <button
            type="button"
            onClick={() => setShowLeaderboard(false)}
            className="px-4 pt-4 text-sm text-ink-muted"
          >
            &larr; Back
          </button>
          <Leaderboard myAddress={visitorAddress} />
        </div>
      )
    } else if (selectedHit) {
      content = (
        <MyQr
          visitorAddress={visitorAddress}
          campaign={selectedHit.campaign}
          attestation={attestation}
          onBack={() => setSelectedHit(null)}
        />
      )
    } else {
      content = (
        <div className="bg-bg">
          <div className="flex justify-end px-4 pt-4">
            <button
              type="button"
              onClick={() => setShowLeaderboard(true)}
              className="text-sm text-brand underline"
            >
              Rankings
            </button>
          </div>
          <Search onSelectCampaign={setSelectedHit} />
        </div>
      )
    }
  }

  return (
    <>
      <LogoutBar />
      {content}
    </>
  )
}

export default App