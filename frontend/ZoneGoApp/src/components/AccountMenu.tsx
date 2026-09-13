import { useEffect, useRef, useState } from 'react'

interface AccountMenuProps {
  onEditProfile: () => void
  onSwitchRole: () => void
  onLogout: () => void
}

export function AccountMenu({ onEditProfile, onSwitchRole, onLogout }: AccountMenuProps) {
  const [open, setOpen] = useState(false)
  const [panel, setPanel] = useState<'about' | 'support' | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label="Account menu"
        className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-surface text-ink-muted"
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
          <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="2" />
          <path
            d="M5 20c0-3.5 3-6 7-6s7 2.5 7 6"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-10 w-52 rounded-2xl border border-border bg-surface py-2 shadow-lg">
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              onEditProfile()
            }}
            className="block w-full px-4 py-2 text-left text-sm text-ink hover:bg-bg"
          >
            Profile
          </button>
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              onSwitchRole()
            }}
            className="block w-full px-4 py-2 text-left text-sm text-ink hover:bg-bg"
          >
            Switch role
          </button>
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              setPanel('about')
            }}
            className="block w-full px-4 py-2 text-left text-sm text-ink hover:bg-bg"
          >
            About
          </button>
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              setPanel('support')
            }}
            className="block w-full px-4 py-2 text-left text-sm text-ink hover:bg-bg"
          >
            Support
          </button>
          <div className="my-1 border-t border-border" />
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              onLogout()
            }}
            className="block w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-bg"
          >
            Log out
          </button>
        </div>
      )}

      {panel && (
        <div
          className="fixed inset-0 z-20 flex items-center justify-center bg-black/30 px-6"
          onClick={() => setPanel(null)}
        >
          <div
            className="w-full max-w-xs rounded-2xl bg-surface p-5 text-center"
            onClick={(event) => event.stopPropagation()}
          >
            {panel === 'about' ? (
              <>
                <h2 className="text-lg font-bold text-ink">About ZoneGo</h2>
                <p className="mt-2 text-sm text-ink-muted">
                  Search for something nearby, walk to the store, and get paid
                  for showing up. The merchant only pays when a verified human
                  walks through their door.
                </p>
              </>
            ) : (
              <>
                <h2 className="text-lg font-bold text-ink">Support</h2>
                <p className="mt-2 text-sm text-ink-muted">
                  Something not working? Reach out to the ZoneGo team through
                  the channel you used to get this build.
                </p>
              </>
            )}
            <button
              type="button"
              onClick={() => setPanel(null)}
              className="mt-4 w-full rounded-full bg-brand py-2 text-sm font-medium text-white"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
