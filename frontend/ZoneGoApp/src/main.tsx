import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { PrivyProvider } from '@privy-io/react-auth'
import { RoleProvider } from './context/RoleContext'
import './index.css'
import App from './App.tsx'

const privyAppId = import.meta.env.VITE_PRIVY_APP_ID

if (!privyAppId) {
  throw new Error(
    'Falta VITE_PRIVY_APP_ID. Creá frontend/ZoneGoApp/.env con esa variable (mirá .env.example).',
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PrivyProvider
      appId={privyAppId}
      config={{
        loginMethods: ['email', 'sms'],
        appearance: {
          theme: 'light',
        },
        embeddedWallets: {
          ethereum: {
            createOnLogin: 'all-users',
          },
        },
      }}
    >
      <RoleProvider>
        <App />
      </RoleProvider>
    </PrivyProvider>
  </StrictMode>,
)