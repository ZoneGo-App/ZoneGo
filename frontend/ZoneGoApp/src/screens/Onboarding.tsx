import { useLogin } from '@privy-io/react-auth'
import { useRole } from '../context/RoleContext'

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
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 text-center">
      <div>
        <h1 className="text-3xl font-bold">ZoneGo</h1>
        <p className="mt-2 text-gray-600">
          Search for something nearby, walk to the store, and get paid for showing up.
        </p>
      </div>

      <div className="flex w-full max-w-xs flex-col gap-3">
        <button
          type="button"
          onClick={enterAsMerchant}
          className="rounded-lg bg-black px-6 py-3 font-medium text-white"
        >
          I'm a merchant
        </button>
        <button
          type="button"
          onClick={enterAsNeighbor}
          className="rounded-lg border border-gray-300 px-6 py-3 font-medium text-gray-900"
        >
          I'm a neighbor
        </button>
      </div>
    </div>
  )
}