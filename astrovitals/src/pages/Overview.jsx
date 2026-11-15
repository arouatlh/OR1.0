import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useSim, SCENARIOS } from '../store/useSim'
import BodyTwin, { REGION_INFO } from '../components/BodyTwin'
import Vital, { VITALS } from '../components/Vital'

const ASTRONAUT_ID = 'astro-a'
const TELEMETRY_URL =
  `/api/v1/astronauts/${ASTRONAUT_ID}/telemetry?limit=20&order=DESC`

export default function Overview() {
  const {
    history: simulatedHistory,
    alerts,
    scenario,
    setScenario,
    region,
    selectRegion,
    log,
    offline,
  } = useSim()

  const [mode, setMode] = useState('backend')
  const [backendHistory, setBackendHistory] = useState([])
  const [telemetryStatus, setTelemetryStatus] = useState('Loading backend readings…')
  const [refreshCount, setRefreshCount] = useState(0)
  const [analysis, setAnalysis] = useState('')
  const [assessment, setAssessment] = useState(null)
  const [analysisError, setAnalysisError] = useState('')
  const [analyzing, setAnalyzing] = useState(false)

  const isBackend = mode === 'backend'

  async function analyzeReadings() {
    if (analyzing || backendHistory.length === 0) return

    const readings = backendHistory.slice(-5).map(({ t, hr, spo2, rr }) => ({
      t,
      hr,
      spo2,
      rr,
    }))

    setAnalyzing(true)
    setAnalysis('')
    setAssessment(null)
    setAnalysisError('')

    try {
      const response = await fetch('/api/v1/ai/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ readings }),
      })

      const result = await response.json().catch(() => null)

      if (!response.ok) {
        throw new Error(
          result?.detail || result?.message || `Analysis failed (HTTP ${response.status})`,
        )
      }

      if (typeof result?.analysis !== 'string' || !result.analysis.trim()) {
        throw new Error('The backend returned no analysis.')
      }

      setAnalysis(result.analysis)
      setAssessment(result.assessment ?? null)
    } catch (error) {
      setAnalysisError(error.message)
    } finally {
      setAnalyzing(false)
    }
  }

  useEffect(() => {
    if (mode !== 'backend') return

    const controller = new AbortController()

    async function loadTelemetry() {
      setTelemetryStatus('Loading backend readings…')

      try {
        const response = await fetch(TELEMETRY_URL, {
          signal: controller.signal,
          cache: 'no-store',
        })

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const { data } = await response.json()
        if (!Array.isArray(data)) {
          throw new Error('Unexpected telemetry response')
        }

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
        setTelemetryStatus(
          readings.length
            ? `Backend telemetry · ${ASTRONAUT_ID}`
            : `No saved readings for ${ASTRONAUT_ID}`,
        )
      } catch (error) {
        if (controller.signal.aborted) return

        setBackendHistory([])
        setTelemetryStatus(`Could not load backend readings (${error.message})`)
      }
    }

    loadTelemetry()
    return () => controller.abort()
  }, [mode, refreshCount])

  const history = isBackend ? backendHistory : simulatedHistory
  const last = history[history.length - 1]
  const active = alerts.filter((alert) => alert.active)

  let state = 'Insufficient data'
  let stateClass = 'nodata'

  if (isBackend) {
    state = 'Backend assessment not connected'
  } else if (last?.hr != null) {
    state = active.length ? 'Review required' : 'No monitoring flags'
    stateClass = active.length ? 'warn' : 'ok'
  }

  return (
    <motion.div
      className="grid"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <section className="card left">
        <h2>Crew profile</h2>
        <dl>
          <dt>Astronaut</dt>
          <dd>{isBackend ? ASTRONAUT_ID : 'AST-001 (demo)'}</dd>

          <dt>Mission</dt>
          <dd>Mars Transit (demo)</dd>

          {isBackend ? (
            <>
              <dt>Telemetry</dt>
              <dd>{telemetryStatus}</dd>
            </>
          ) : (
            <>
              <dt>Wearable</dt>
              <dd>
                AV-WATCH-001 {last?.hr == null ? '· no signal' : '· connected'}
              </dd>

              <dt>Earth link</dt>
              <dd>{offline ? 'Lost, operating locally' : 'Nominal'}</dd>
            </>
          )}
        </dl>

        {!isBackend && (
          <>
            <h2>Crew-state assessment</h2>
            <p className={`state ${stateClass}`}>{state}</p>
            <p className="meta">
              Illustrative demo assessment. Not a diagnosis or EVA medical clearance.
            </p>
          </>
        )}
      </section>

      <section className="card center">
        <BodyTwin />
        <div className="regioninfo">
          <strong>{region ? region.replace('-', ' ') : 'Select a region'}</strong>
          <p>
            {region
              ? REGION_INFO[region]
              : 'Click the body to inspect. Anatomical visualization only, not a medical scan.'}
          </p>
          {region && <button onClick={() => selectRegion(null)}>Clear</button>}
        </div>
      </section>

      <section className="right">
        <div className="btns">
          <button
            className={isBackend ? 'on' : ''}
            aria-pressed={isBackend}
            onClick={() => setMode('backend')}
          >
            Backend
          </button>
          <button
            className={!isBackend ? 'on' : ''}
            aria-pressed={!isBackend}
            onClick={() => setMode('simulator')}
          >
            Simulator
          </button>
          {isBackend && (
            <button onClick={() => setRefreshCount((count) => count + 1)}>
              Refresh readings
            </button>
          )}
        </div>

        {isBackend && <p className="meta" role="status">{telemetryStatus}</p>}
        {VITALS.map((vital) => (
          <Vital key={vital.k} {...vital} history={history} />
        ))}

        {isBackend && (
          <div className="card">
            <h2>AI Analysis</h2>
            <p className="meta">
              Sends up to five recent readings to Gemini. Use simulated demo readings here.
            </p>
            <button
              type="button"
              onClick={analyzeReadings}
              disabled={analyzing || backendHistory.length === 0}
            >
              {analyzing ? 'Analyzing…' : 'Analyze readings'}
            </button>
            {analysisError && <p role="alert">{analysisError}</p>}
            {analysis && (
              <p role="status">
                <strong>Summary of submitted readings</strong><br />
                {analysis}
              </p>
            )}

            {analysis && (
              <div>
                <h3>Rule-based demo assessment</h3>
                {assessment ? (
                  <>
                    <p>Risk level: <strong>{assessment.risk_level}</strong></p>
                    {assessment.reasons?.length > 0 && (
                      <ul>
                        {assessment.reasons.map((reason, index) => (
                          <li key={index}>{reason}</li>
                        ))}
                      </ul>
                    )}
                  </>
                ) : (
                  <p>Assessment unavailable for this reading.</p>
                )}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="card bottom">
        <div>
          <h2>Scenario simulator</h2>
          {isBackend && <p className="meta">Switch to Simulator to run a demo scenario.</p>}
          <div className="btns">
            {Object.entries(SCENARIOS).map(([key, name]) => (
              <button
                key={key}
                className={scenario === key ? 'on' : ''}
                disabled={isBackend}
                onClick={() => setScenario(key)}
              >
                {name}
              </button>
            ))}
          </div>
        </div>

        <div>
          <h2>Alerts</h2>
          {isBackend ? (
            <p className="meta">Backend alerts are not connected here yet.</p>
          ) : alerts.length === 0 ? (
            <p className="meta">No alerts recorded.</p>
          ) : (
            alerts.slice(0, 3).map((alert) => (
              <p
                key={alert.id}
                className={alert.active ? 'warn' : 'meta'}
                role={alert.active ? 'alert' : undefined}
              >
                {alert.active ? '● ' : '○ '}
                {alert.title}: {alert.detail}
              </p>
            ))
          )}
        </div>

        <div>
          <h2>Recent events</h2>
          {isBackend ? (
            <p className="meta">Backend events are not connected here yet.</p>
          ) : (
            log.slice(0, 4).map((event) => (
              <p key={event.id} className="meta">
                {event.ts.slice(11, 19)}Z · {event.message}
              </p>
            ))
          )}
        </div>
      </section>
    </motion.div>
  )
}