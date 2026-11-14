import { LineChart, Line, YAxis, ResponsiveContainer } from 'recharts'
export default function Vital({ label, unit, k, history, ok, digits = 0 }) {
  const last = history[history.length - 1]; const v = last?.[k]
  const status = v == null ? 'NO DATA' : ok(v) ? 'IN RANGE' : 'REVIEW'
  const cls = v == null ? 'nodata' : ok(v) ? 'ok' : 'warn'
  return (
    <div className="card vital" aria-label={`${label} ${v ?? 'no data'} ${unit}`}>
      <div className="vh"><span>{label}</span><span className={`pill ${cls}`}>{status}</span></div>
      <div className="vv">{v == null ? '—' : v.toFixed(digits)} <small>{unit}</small></div>
      <ResponsiveContainer width="100%" height={40}>
        <LineChart data={history.slice(-40)}><YAxis hide domain={['auto', 'auto']} />
          <Line dataKey={k} stroke="#35D5FF" dot={false} strokeWidth={1.5} isAnimationActive={false} connectNulls={false} /></LineChart>
      </ResponsiveContainer>
      <div className="meta">SIMULATED · {last ? new Date(last.t).toISOString().slice(11, 19) + 'Z' : '--'}</div>
    </div>
  )
}
export const VITALS = [
  { label: 'Heart rate', unit: 'BPM', k: 'hr', ok: (v) => v >= 50 && v <= 100 },
  { label: 'SpO₂', unit: '%', k: 'spo2', ok: (v) => v >= 95 },
  { label: 'Skin temp', unit: '°C', k: 'temp', ok: (v) => v >= 35.5 && v <= 37.2, digits: 1 },
  { label: 'Resp. rate', unit: '/min', k: 'rr', ok: (v) => v >= 12 && v <= 20 },
]
