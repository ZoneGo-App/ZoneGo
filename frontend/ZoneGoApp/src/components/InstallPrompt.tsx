import { useEffect, useState } from 'react'

/**
 * Chrome's install event is not in the DOM typings, so it is declared here
 * rather than cast away at the call site.
 */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

const DISMISSED_KEY = 'zonego_install_dismissed'

function isStandalone(): boolean {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    // iOS reports it here instead, and only on Safari.
    (window.navigator as unknown as { standalone?: boolean }).standalone === true
  )
}

function isIos(): boolean {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent)
}

/**
 * A bar offering to install the app, instead of leaving it buried in the
 * browser menu.
 *
 * Two paths, because the platforms differ. Chrome fires `beforeinstallprompt`
 * once the app qualifies; holding on to that event is what lets a button of
 * ours open the real install dialog later. Safari fires nothing at all and
 * has no API for this, so on iOS the only honest thing is to say where the
 * option lives.
 *
 * Dismissing is remembered. An install bar that comes back on every visit is
 * the kind of thing people close without reading, twice.
 */
export function InstallPrompt() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null)
  const [showIosHint, setShowIosHint] = useState(false)

  useEffect(() => {
    if (isStandalone()) return
    if (localStorage.getItem(DISMISSED_KEY)) return

    if (isIos()) {
      setShowIosHint(true)
      return
    }

    function onBeforeInstall(e: Event) {
      // Without this Chrome shows its own mini-infobar and never hands the
      // event over, so the button below would have nothing to open.
      e.preventDefault()
      setDeferred(e as BeforeInstallPromptEvent)
    }

    window.addEventListener('beforeinstallprompt', onBeforeInstall)
    return () => window.removeEventListener('beforeinstallprompt', onBeforeInstall)
  }, [])

  function dismiss() {
    localStorage.setItem(DISMISSED_KEY, '1')
    setDeferred(null)
    setShowIosHint(false)
  }

  async function install() {
    if (!deferred) return
    await deferred.prompt()
    await deferred.userChoice
    // The event is single use: Chrome will not let the same one open the
    // dialog twice, so it goes either way.
    setDeferred(null)
  }

  if (!deferred && !showIosHint) return null

  return (
    <div className="fixed bottom-20 left-3 right-3 z-40 rounded-2xl border border-border bg-surface p-4 shadow-lg">
      <div className="flex items-start gap-3">
        <img src="/icon-192.png" alt="" className="h-10 w-10 rounded-xl" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-ink">Install ZoneGo</p>
          {showIosHint ? (
            <p className="mt-0.5 text-xs text-ink-muted">
              Tap Share, then &ldquo;Add to Home Screen&rdquo;.
            </p>
          ) : (
            <p className="mt-0.5 text-xs text-ink-muted">
              Keep it on your home screen for when you are out walking.
            </p>
          )}
        </div>
      </div>

      <div className="mt-3 flex gap-2">
        {!showIosHint && (
          <button
            type="button"
            onClick={install}
            className="flex-1 rounded-full bg-brand py-2 text-sm font-medium text-white"
          >
            Install
          </button>
        )}
        <button
          type="button"
          onClick={dismiss}
          className="flex-1 rounded-full border border-border py-2 text-sm font-medium text-ink"
        >
          Not now
        </button>
      </div>
    </div>
  )
}
