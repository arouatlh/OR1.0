import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { useSim } from '../store/useSim'
import { VITALS } from '../components/Vital'
export default function Monitoring() {
  const { history, paused, togglePause } = useSim()
  const data = history.map((h) => ({ ...h, time: new Date(h.t).toISOString().slice(11, 19) }))
  return (
    <div>
      <div className="btns"><button onClick={togglePause}>{paused ? 'Resume' : 'Pause'} live simulation</button>
        {history.some((h) => h.hr == null) && <span className="pill nodata">Missing data appears as gaps, never as healthy values</span>}</div>
      <div className="charts">{VITALS.map((v) => (
        <div className="card" key={v.k}><h2>{v.label} ({v.unit}) <span className="meta">SIMULATED</span></h2>
          <ResponsiveContainer width="100%" height={200}><LineChart data={data}><CartesianGrid stroke="#10243A" /><XAxis dataKey="time" stroke="#91AFC4" fontSize={10} /><YAxis stroke="#91AFC4" fontSize={10} domain={['auto', 'auto']} />
            <Tooltip contentStyle={{ background: '#091827', border: '1px solid #35D5FF33' }} /><Line dataKey={v.k} stroke="#35D5FF" dot={false} isAnimationActive={false} connectNulls={false} /></LineChart></ResponsiveContainer></div>))}</div>
    </div>
  )
}
