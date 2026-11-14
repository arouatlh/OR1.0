import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { useSim } from '../store/useSim'
import { VITALS } from '../components/Vital'

const TELEMETRY_URL = '/api/v1/astronauts/astro-a/telemetry?limit=20&order=DESC'

export default function Monitoring() {
  const { history: simulatedHistory, paused, togglePause } = useSim()
  const [mode, setMode] = useState('backend')
  const [backendHistory, setBackendHistory] = useState([])
  const [status, setStatus] = useState('Loading backend readings…')
  const [refreshCount, setRefreshCount] = useState(0)
  const isBackend = mode === 'backend'

  useEffect(() => {
    if (!isBackend) return

    const controller = new AbortController()
    setStatus('Loading backend readings…')

    async function loadTelemetry() {
      try {
        const response = await fetch(TELEMETRY_URL, {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)

        const { data } = await response.json()
        if (!Array.isArray(data)) throw new Error('Unexpected telemetry response')

        const readings = data
          .map((sample) => ({
            t: Date.parse(sample.recorded_at),
            hr: sample.heart_rate ?? null,
            spo2: sample.spo2 ?? null,
            rr: sample.resp_rate ?? null,
            temp: null,
          }))
          .filter((reading) => Number.isFinite(reading.t))
          .sort((a, b) => a.t - b.t)

        if (controller.signal.aborted) return

        setBackendHistory(readings)
        setStatus(readings.length
          ? 'Backend telemetry · astro-a'
          : 'No saved readings for astro-a')
      } catch (error) {
        if (controller.signal.aborted) return
        setBackendHistory([])
        setStatus(`Could not load backend readings (${error.message})`)
      }
    }

    loadTelemetry()
    return () => controller.abort()
  }, [isBackend, refreshCount])

  const history = isBackend ? backendHistory : simulatedHistory
  const latest = history[history.length - 1]
  const data = history.map((reading) => ({
    ...reading,
    time: new Date(reading.t).toISOString().slice(11, 19),
  }))

  return (
    <div>
      <div className="btns">
        <button
          aria-pressed={isBackend}
          onClick={() => setMode('backend')}
        >
          Backend
        </button>
        <button
          aria-pressed={!isBackend}
          onClick={() => setMode('simulator')}
        >
          Simulator
        </button>
        {isBackend ? (
          <button onClick={() => setRefreshCount((count) => count + 1)}>
            Refresh readings
          </button>
        ) : (
          <button onClick={togglePause}>
            {paused ? 'Resume' : 'Pause'} live simulation
          </button>
        )}
      </div>

      {isBackend && <p className="meta" role="status">{status}</p>}

      <div className="charts">
        {VITALS.map((vital) => (
          <div className="card" key={vital.k}>
            <h2>
              {vital.label} ({vital.unit}){' '}
              <span className="meta">{isBackend ? 'BACKEND' : 'SIMULATED'}</span>
            </h2>
            <p className="meta">
              {latest?.[vital.k] == null
                ? 'Latest reading unavailable'
                : `Latest: ${latest[vital.k]} ${vital.unit}`}
            </p>

            {data.some((reading) => reading[vital.k] != null) && (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={data}>
                  <CartesianGrid stroke="#10243A" />
                  <XAxis dataKey="time" stroke="#91AFC4" fontSize={10} />
                  <YAxis stroke="#91AFC4" fontSize={10} domain={['auto', 'auto']} />
                  <Tooltip contentStyle={{ background: '#091827', border: '1px solid #35D5FF33' }} />
                  <Line
                    dataKey={vital.k}
                    stroke="#35D5FF"
                    dot={data.length === 1}
                    isAnimationActive={false}
                    connectNulls={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}