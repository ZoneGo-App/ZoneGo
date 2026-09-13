import logo from '../assets/logo.png'

export function Header() {
  return (
    <div className="flex items-center gap-2 bg-bg px-4 pt-4">
      <img src={logo} alt="ZoneGo" className="h-7 w-7" />
      <span className="text-lg font-bold text-ink">ZoneGo</span>
    </div>
  )
}