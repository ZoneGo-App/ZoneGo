import { createContext, useContext, useState, type ReactNode } from 'react'

export type Role = 'comercio' | 'vecino' | null

const STORAGE_KEY = 'zonego_role'

function readStoredRole(): Role {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'comercio' || stored === 'vecino' ? stored : null
}

interface RoleContextValue {
  role: Role
  setRole: (role: Role) => void
}

const RoleContext = createContext<RoleContextValue | undefined>(undefined)

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>(readStoredRole)

  const setRole = (newRole: Role) => {
    setRoleState(newRole)
    if (newRole) {
      localStorage.setItem(STORAGE_KEY, newRole)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  return (
    <RoleContext.Provider value={{ role, setRole }}>
      {children}
    </RoleContext.Provider>
  )
}

export function useRole() {
  const ctx = useContext(RoleContext)
  if (!ctx) {
    throw new Error('useRole tiene que usarse dentro de RoleProvider')
  }
  return ctx
}