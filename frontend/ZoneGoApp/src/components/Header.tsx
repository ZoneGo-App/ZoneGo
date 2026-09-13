import logo from '../assets/logo.png'
import { useRole } from '../context/RoleContext'

export function Header() {
  const { role, setRole } = useRole()

  return (
    <div className="flex items-center justify-between bg-bg px-4 pt-4">
      <div className="flex items-center gap-2">
        <img src={logo} alt="ZoneGo" className="h-7 w-7" />
        <span className="text-lg font-bold text-ink">ZoneGo</span>
      </div>
      {role && (
        <button
          type="button"
          onClick={() => setRole(null)}
          className="text-xs text-ink-muted underline"
        >
          Switch role
        </button>
      )}
    </div>
  )
}