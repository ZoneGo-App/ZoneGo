import { useLogin } from '@privy-io/react-auth'
import { useRole } from '../context/RoleContext'
import logo from '../assets/logo.png'

export function Onboarding() {
  const { setRole } = useRole()
  const { login } = useLogin()

  const enterAsMerchant = () => {
    setRole('comercio')
    login({ loginMethods: ['email'] })
  }

  const enterAsNeighbor = () => {
    setRole('vecino')
    login({ loginMethods: ['sms', 'email'] })
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 bg-bg px-6 text-center">
      <div className="flex flex-col items-center gap-3">
        <img src={logo} alt="ZoneGo" className="h-14 w-14" />
        <h1 className="text-3xl font-bold text-ink">ZoneGo</h1>
        <p className="max-w-xs text-ink-muted">
          Search for something nearby, walk to the store, and get paid for showing up.
        </p>
      </div>

      <div className="flex w-full max-w-xs flex-col gap-3">
        <button
          type="button"
          onClick={enterAsNeighbor}
          className="rounded-2xl border border-border bg-surface p-4 text-left transition hover:border-brand"
        >
          <p className="font-semibold text-ink">I'm a neighbor</p>
          <p className="mt-1 text-sm text-ink-muted">
            Walk to nearby stores and get paid for showing up.
          </p>
        </button>
        <button
          type="button"
          onClick={enterAsMerchant}
          className="rounded-2xl border border-border bg-surface p-4 text-left transition hover:border-brand"
        >
          <p className="font-semibold text-ink">I'm a merchant</p>
          <p className="mt-1 text-sm text-ink-muted">
            Pay only when a verified person walks into your shop.
          </p>
        </button>
      </div>

      <p className="max-w-xs text-xs text-ink-muted">
        Your balance is always shown in dollars. No crypto jargon.
      </p>
    </div>
  )
}