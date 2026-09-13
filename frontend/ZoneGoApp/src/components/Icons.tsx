interface IconProps {
  active: boolean
}

export function ExploreIcon({ active }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth={active ? 2.5 : 2} />
      <path d="M20 20l-4.3-4.3" stroke="currentColor" strokeWidth={active ? 2.5 : 2} strokeLinecap="round" />
    </svg>
  )
}

export function QrIcon({ active }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <rect x="3" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth={active ? 2.5 : 2} />
      <rect x="14" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth={active ? 2.5 : 2} />
      <rect x="3" y="14" width="7" height="7" rx="1" stroke="currentColor" strokeWidth={active ? 2.5 : 2} />
      <path d="M14 14h3v3h-3zM19 19h2v2h-2z" fill="currentColor" />
    </svg>
  )
}

export function PanelIcon({ active }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth={active ? 2.5 : 2} />
      <path d="M5 20c0-3.5 3-6 7-6s7 2.5 7 6" stroke="currentColor" strokeWidth={active ? 2.5 : 2} strokeLinecap="round" />
    </svg>
  )
}

export function RankingIcon({ active }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path
        d="M8 21h8M12 17v4M7 4h10v4a5 5 0 0 1-10 0V4ZM7 6H4v1a3 3 0 0 0 3 3M17 6h3v1a3 3 0 0 1-3 3"
        stroke="currentColor"
        strokeWidth={active ? 2.5 : 2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function ScanIcon({ active }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path
        d="M4 8V5a1 1 0 0 1 1-1h3M20 8V5a1 1 0 0 0-1-1h-3M4 16v3a1 1 0 0 0 1 1h3M20 16v3a1 1 0 0 1-1 1h-3M7 12h10"
        stroke="currentColor"
        strokeWidth={active ? 2.5 : 2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}