import { useRole } from '../context/RoleContext'
import { usePrivy } from '@privy-io/react-auth'
import { AccountMenu } from './AccountMenu'

const ATTESTATION_STORAGE_KEY = 'zonego_attestation'

interface HeaderProps {
  onEditProfile?: () => void
}

export function Header({ onEditProfile }: HeaderProps) {
  const { role, setRole } = useRole()
  const { logout } = usePrivy()

  async function handleLogout() {
    setRole(null)
    localStorage.removeItem(ATTESTATION_STORAGE_KEY)
    await logout()
  }

  return (
    <div className="flex items-center justify-between bg-bg px-4 pt-4">
      <span className="text-lg font-bold text-ink">ZoneGo</span>
      {role && (
        <AccountMenu
          onEditProfile={onEditProfile ?? (() => {})}
          onSwitchRole={() => setRole(null)}
          onLogout={handleLogout}
        />
      )}
    </div>
  )
}