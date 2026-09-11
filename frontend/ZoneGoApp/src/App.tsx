import { useState } from 'react'
import { usePrivy } from '@privy-io/react-auth'
import { useRole } from './context/RoleContext'
import { Onboarding } from './screens/Onboarding'
import { Search } from './screens/Search'
import { MyQr } from './screens/MyQr'
import { ScanQr } from './screens/ScanQr'
import type { SearchHit } from './lib/api'

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
  const [selectedHit, setSelectedHit] = useState<SearchHit | null>(null)

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

  // Merchant side. "My panel" doesn't exist yet — scanning stands in as the
  // merchant's only screen until it's built.
  if (role === 'comercio') {
    return <ScanQr />
  }

  // Neighbor side.
  if (selectedHit) {
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
    return (
      <MyQr
        visitorAddress={visitorAddress}
        campaign={selectedHit.campaign}
        onBack={() => setSelectedHit(null)}
      />
    )
  }

  return <Search onSelectCampaign={setSelectedHit} />
}

export default App