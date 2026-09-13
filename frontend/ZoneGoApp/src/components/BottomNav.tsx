import type { ComponentType } from 'react'

interface Tab<T extends string> {
  id: T
  label: string
  Icon: ComponentType<{ active: boolean }>
}

interface BottomNavProps<T extends string> {
  tabs: Tab<T>[]
  activeTab: T
  onSelect: (tab: T) => void
}

export function BottomNav<T extends string>({ tabs, activeTab, onSelect }: BottomNavProps<T>) {
  return (
    <nav className="fixed inset-x-0 bottom-0 border-t border-border bg-surface pb-[env(safe-area-inset-bottom)]">
      <div className="mx-auto flex max-w-md items-center justify-around px-2 py-2">
        {tabs.map(({ id, label, Icon }) => {
          const isActive = activeTab === id
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelect(id)}
              className={`flex flex-col items-center gap-1 rounded-xl px-3 py-1.5 ${
                isActive ? 'text-brand' : 'text-ink-muted'
              }`}
            >
              <Icon active={isActive} />
              <span className="text-[11px] font-medium">{label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}