import { usePrivy } from '@privy-io/react-auth'
import { useRole } from './context/RoleContext'
import { Onboarding } from './screens/Onboarding'
import { Search } from './screens/Search'

function RoleFallback() {
  const { setRole } = useRole()
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="text-gray-600">No pudimos recordar tu rol. ¿Cómo entrás?</p>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => setRole('comercio')}
          className="rounded-lg bg-black px-6 py-3 font-medium text-white"
        >
          Soy un comercio
        </button>
        <button
          type="button"
          onClick={() => setRole('vecino')}
          className="rounded-lg border border-gray-300 px-6 py-3 font-medium text-gray-900"
        >
          Soy un vecino
        </button>
      </div>
    </div>
  )
}

function App() {
  const { ready, authenticated } = usePrivy()
  const { role } = useRole()

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Cargando...</p>
      </div>
    )
  }

  if (!authenticated) {
    return <Onboarding />
  }

  if (!role) {
    return <RoleFallback />
  }

  return <Search />
}

export default App