import { useLogin } from '@privy-io/react-auth'
import { useRole } from '../context/RoleContext'

export function Onboarding() {
  const { setRole } = useRole()
  const { login } = useLogin()

  const entrarComoComercio = () => {
    setRole('comercio')
    login({ loginMethods: ['email'] })
  }

  const entrarComoVecino = () => {
    setRole('vecino')
    login({ loginMethods: ['sms', 'email'] })
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 text-center">
      <div>
        <h1 className="text-3xl font-bold">ZoneGo</h1>
        <p className="mt-2 text-gray-600">
          Buscá algo cerca, caminá hasta el local, y te pagan por haber ido.
        </p>
      </div>

      <div className="flex w-full max-w-xs flex-col gap-3">
        <button
          type="button"
          onClick={entrarComoComercio}
          className="rounded-lg bg-black px-6 py-3 font-medium text-white"
        >
          Soy un comercio
        </button>
        <button
          type="button"
          onClick={entrarComoVecino}
          className="rounded-lg border border-gray-300 px-6 py-3 font-medium text-gray-900"
        >
          Soy un vecino
        </button>
      </div>
    </div>
  )
}