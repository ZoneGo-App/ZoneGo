import { useEffect, useState } from 'react'
import { usePrivy } from '@privy-io/react-auth'
import { useRole } from './context/RoleContext'
import { Header } from './components/Header'
import { BottomNav } from './components/BottomNav'
import { ExploreIcon, QrIcon, PanelIcon, RankingIcon, ScanIcon } from './components/Icons'
import { MyPanel } from './screens/MyPanel'
import { Onboarding } from './screens/Onboarding'
import { Search } from './screens/Search'
import { MyQr } from './screens/MyQr'
import { ScanQr } from './screens/ScanQr'
import { MerchantPanel } from './screens/MerchantPanel'
import { MerchantRanking } from './screens/MerchantRanking'
import { MerchantProfileForm } from './screens/MerchantProfileForm'
import { VisitorProfileForm } from './screens/VisitorProfileForm'
import { IdentityCheck } from './screens/IdentityCheck'
import { Leaderboard } from './screens/Leaderboard'
import type { SearchHit, WorldAttestation } from './lib/api'
import {
  readMerchantProfile,
  readVisitorProfile,
  type MerchantProfile,
  type VisitorProfile,
} from './lib/profile'

const ATTESTATION_STORAGE_KEY = 'zonego_attestation'

type NeighborTab = 'explore' | 'myqr' | 'panel' | 'ranking'
type MerchantTab = 'scan' | 'panel' | 'ranking'

/**
 * Reads a previously stored attestation, but only if it hasn't expired.
 * The attestation itself carries a TTL set server-side (originally 120s,
 * pending an extension from Lucio) — an expired one sitting in storage
 * would just fail on chain, so there is no point handing it back to the UI
 * as if it were still usable. Uses localStorage (not sessionStorage) so it
 * survives closing the tab or the app — but as long as the server-side TTL
 * stays at 120s, a refresh after that window will still ask again. That is
 * expected until the TTL itself is extended, not a storage bug.
 */
function readStoredAttestation(): WorldAttestation | null {
  const raw = localStorage.getItem(ATTESTATION_STORAGE_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as WorldAttestation
    if (parsed.expiry <= Math.floor(Date.now() / 1000)) {
      localStorage.removeItem(ATTESTATION_STORAGE_KEY)
      return null
    }
    return parsed
  } catch {
    return null
  }
}

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

function App() {
  const { ready, authenticated, user } = usePrivy()
  const { role } = useRole()
  const [attestation, setAttestationState] = useState<WorldAttestation | null>(
    readStoredAttestation,
  )
  const [selectedHit, setSelectedHit] = useState<SearchHit | null>(null)
  const [neighborTab, setNeighborTab] = useState<NeighborTab>('explore')
  const [merchantTab, setMerchantTab] = useState<MerchantTab>('panel')
  const [merchantProfile, setMerchantProfile] = useState<MerchantProfile | null>(null)
  const [visitorProfile, setVisitorProfile] = useState<VisitorProfile | null>(null)
  const [editingProfile, setEditingProfile] = useState(false)

  const merchantAddress = import.meta.env.VITE_DEV_MERCHANT_ADDRESS || user?.wallet?.address || ''
  const visitorAddress = user?.wallet?.address

  useEffect(() => {
    if (role === 'comercio' && merchantAddress) {
      setMerchantProfile(readMerchantProfile(merchantAddress))
    }
  }, [role, merchantAddress])

  useEffect(() => {
    if (role === 'vecino' && visitorAddress) {
      setVisitorProfile(readVisitorProfile(visitorAddress))
    }
  }, [role, visitorAddress])

  function setAttestation(next: WorldAttestation) {
    localStorage.setItem(ATTESTATION_STORAGE_KEY, JSON.stringify(next))
    setAttestationState(next)
  }

  function handleSelectCampaign(hit: SearchHit) {
    setSelectedHit(hit)
    setNeighborTab('myqr')
  }

  function handleBackFromQr() {
    setSelectedHit(null)
    setNeighborTab('explore')
  }

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

  if (!role) {
    return <RoleFallback />
  }

  let content: React.ReactNode

  if (role === 'comercio') {
    if (!merchantAddress) {
      content = (
        <p className="px-6 pt-10 text-center text-red-600">
          No wallet found for your account yet. Try signing out and back in.
        </p>
      )
    } else if (!merchantProfile || editingProfile) {
      content = (
        <MerchantProfileForm
          merchantAddress={merchantAddress}
          initialProfile={merchantProfile}
          onComplete={(profile) => {
            setMerchantProfile(profile)
            setEditingProfile(false)
          }}
        />
      )
    } else {
      let merchantTabContent: React.ReactNode

      if (merchantTab === 'scan') {
        merchantTabContent = <ScanQr />
      } else if (merchantTab === 'ranking') {
        merchantTabContent = <MerchantRanking />
      } else {
        merchantTabContent = <MerchantPanel merchantAddress={merchantAddress} />
      }

      content = (
        <div className="pb-20">
          {merchantTabContent}
          <BottomNav
            tabs={[
              { id: 'scan', label: 'Scan', Icon: ScanIcon },
              { id: 'panel', label: 'My Panel', Icon: PanelIcon },
              { id: 'ranking', label: 'Ranking', Icon: RankingIcon },
            ]}
            activeTab={merchantTab}
            onSelect={setMerchantTab}
          />
        </div>
      )
    }
  } else if (!visitorAddress) {
    content = (
      <p className="px-6 pt-10 text-center text-red-600">
        No wallet found for your account yet. Try signing out and back in.
      </p>
    )
  } else if (!attestation) {
    content = <IdentityCheck visitorAddress={visitorAddress} onVerified={setAttestation} />
  } else if (!visitorProfile || editingProfile) {
    content = (
      <VisitorProfileForm
        visitorAddress={visitorAddress}
        initialProfile={visitorProfile}
        onComplete={(profile) => {
          setVisitorProfile(profile)
          setEditingProfile(false)
        }}
      />
    )
  } else {
    let tabContent: React.ReactNode

    if (neighborTab === 'myqr' && selectedHit) {
      tabContent = (
        <MyQr
          visitorAddress={visitorAddress}
          campaign={selectedHit.campaign}
          attestation={attestation}
          onBack={handleBackFromQr}
        />
      )
    } else if (neighborTab === 'myqr') {
      tabContent = (
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2 px-6 text-center">
          <p className="text-ink">No active QR yet.</p>
          <p className="text-sm text-ink-muted">Search for a place and pick one to get your code.</p>
          <button
            type="button"
            onClick={() => setNeighborTab('explore')}
            className="mt-2 rounded-full bg-brand px-6 py-2 text-sm font-medium text-white"
          >
            Explore nearby
          </button>
        </div>
      )
    } else if (neighborTab === 'panel') {
      tabContent = <MyPanel />
    } else if (neighborTab === 'ranking') {
      tabContent = <Leaderboard myAddress={visitorAddress} />
    } else {
      tabContent = <Search onSelectCampaign={handleSelectCampaign} />
    }

    content = (
      <div className="pb-20">
        {tabContent}
        <BottomNav
          tabs={[
            { id: 'explore', label: 'Explore', Icon: ExploreIcon },
            { id: 'myqr', label: 'My QR', Icon: QrIcon },
            { id: 'panel', label: 'My Panel', Icon: PanelIcon },
            { id: 'ranking', label: 'Ranking', Icon: RankingIcon },
          ]}
          activeTab={neighborTab}
          onSelect={setNeighborTab}
        />
      </div>
    )
  }

  return (
    <>
      <Header onEditProfile={() => setEditingProfile(true)} />
      {content}
    </>
  )
}

export default App