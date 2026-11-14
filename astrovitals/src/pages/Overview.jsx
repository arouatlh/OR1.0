import { motion } from 'framer-motion'
import { useSim, SCENARIOS } from '../store/useSim'
import BodyTwin, { REGION_INFO } from '../components/BodyTwin'
import Vital, { VITALS } from '../components/Vital'
export default function Overview() {
  const { history, alerts, scenario, setScenario, region, selectRegion, log, offline } = useSim()
  const active = alerts.filter((a) => a.active)
  const last = history[history.length - 1]
  const state = !last || last.hr == null ? 'Insufficient data' : active.length ? 'Review required' : 'No monitoring flags'
  return (
    <motion.div className="grid" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <section className="card left">
        <h2>Crew profile</h2>
        <dl><dt>Astronaut</dt><dd>AST-001 (demo)</dd><dt>Mission</dt><dd>Mars Transit (demo)</dd><dt>Wearable</dt><dd>AV-WATCH-001 {last?.hr == null ? '· no signal' : '· connected'}</dd>
          <dt>Earth link</dt><dd>{offline ? 'Lost, operating locally' : 'Nominal'}</dd></dl>
        <h2>Crew-state assessment</h2>
        <p className={`state ${active.length ? 'warn' : last?.hr == null ? 'nodata' : 'ok'}`}>{state}</p>
        <p className="meta">Illustrative demo assessment. Not a diagnosis or EVA medical clearance.</p>
      </section>
      <section className="card center">
        <BodyTwin />
        <div className="regioninfo"><strong>{region ? region.replace('-', ' ') : 'Select a region'}</strong>
          <p>{region ? REGION_INFO[region] : 'Click the body to inspect. Anatomical visualization only, not a medical scan.'}</p>
          {region && <button onClick={() => selectRegion(null)}>Clear</button>}</div>
      </section>
      <section className="right">{VITALS.map((v) => <Vital key={v.k} {...v} history={history} />)}</section>
      <section className="card bottom">
        <div><h2>Scenario simulator</h2>
          <div className="btns">{Object.entries(SCENARIOS).map(([k, n]) => <button key={k} className={scenario === k ? 'on' : ''} onClick={() => setScenario(k)}>{n}</button>)}</div></div>
        <div><h2>Alerts</h2>{alerts.length === 0 ? <p className="meta">No alerts recorded.</p> : alerts.slice(0, 3).map((a) => <p key={a.id} className={a.active ? 'warn' : 'meta'} role={a.active ? 'alert' : undefined}>{a.active ? '● ' : '○ '}{a.title}: {a.detail}</p>)}</div>
        <div><h2>Recent events</h2>{log.slice(0, 4).map((e) => <p key={e.id} className="meta">{e.ts.slice(11, 19)}Z · {e.message}</p>)}</div>
      </section>
    </motion.div>
  )
}
