import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { PrivyProvider } from '@privy-io/react-auth'
import { RoleProvider } from './context/RoleContext'
import './index.css'
import App from './App.tsx'

const privyAppId = import.meta.env.VITE_PRIVY_APP_ID

// Registered only in a real build. In dev it would sit between Vite's hot
// reload and the page for no benefit.
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // An install prompt that never appears is not worth an error to the user.
    })
  })
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