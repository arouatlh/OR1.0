import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { Activity, HeartPulse, Wifi, WifiOff, Bell } from 'lucide-react'
import { useSim } from './store/useSim'
import Overview from './pages/Overview'
import Monitoring from './pages/Monitoring'
export default function App() {
  const { tick, offline, toggleOffline, alerts } = useSim()
  const [now, setNow] = useState(new Date())
  useEffect(() => { const a = setInterval(tick, 1000), b = setInterval(() => setNow(new Date()), 1000); return () => { clearInterval(a); clearInterval(b) } }, [tick])
  return (
    <div className="app">
      <header className="top"><strong className="logo"><HeartPulse size={18} /> AstroVitals</strong><span>Mars Transit (demo) · AST-001</span>
        <span>{now.toISOString().slice(0, 19)}Z</span><span className="pill warn">SIMULATED</span>
        <button onClick={toggleOffline} aria-pressed={offline}>{offline ? <WifiOff size={14} /> : <Wifi size={14} />} {offline ? 'OFFLINE' : 'ONLINE'}</button>
        <span><Bell size={14} /> {alerts.filter((a) => a.active).length} active</span></header>
      <nav className="side" aria-label="Main"><NavLink to="/" end><Activity size={16} /> Mission Overview</NavLink><NavLink to="/monitoring"><HeartPulse size={16} /> Health Monitoring</NavLink></nav>
      <main><Routes><Route path="/" element={<Overview />} /><Route path="/monitoring" element={<Monitoring />} /></Routes>
        <p className="meta foot">Prototype with simulated data. Not a medical diagnosis system. Digital twin is a visualization, not a scan.</p></main>
    </div>
  )
}
