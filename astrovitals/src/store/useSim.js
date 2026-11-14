import { create } from 'zustand'
// ALL DATA HERE IS SIMULATED. Replace tick() with validated backend readings later.
const TARGETS = {
  normal:   { hr: 74,  spo2: 98, temp: 36.5, rr: 15 },
  elevated: { hr: 108, spo2: 96, temp: 36.9, rr: 21 },
  anomaly:  { hr: 134, spo2: 93, temp: 37.4, rr: 27 },
  recovery: { hr: 82,  spo2: 97, temp: 36.6, rr: 17 },
  missing:  null,
}
export const SCENARIOS = { normal: 'Normal', elevated: 'Elevated response', anomaly: 'Simulated anomaly', missing: 'Missing sensor data', recovery: 'Recovery' }
const loadLog = () => { try { return JSON.parse(localStorage.getItem('av_log') || '[]') } catch { return [] } }
const saveLog = (l) => { try { localStorage.setItem('av_log', JSON.stringify(l.slice(0, 500))) } catch {} }
const ev = (severity, type, message) => ({ id: crypto.randomUUID(), ts: new Date().toISOString(), severity, type, message, source: 'simulated' })
export const useSim = create((set, get) => ({
  scenario: 'normal', paused: false, offline: false, history: [], alerts: [], log: loadLog(), region: null,
  addEvent: (sev, type, msg) => { const log = [ev(sev, type, msg), ...get().log]; saveLog(log); set({ log }) },
  setScenario: (s) => { set({ scenario: s }); get().addEvent('info', 'scenario', `Scenario set: ${SCENARIOS[s]} (simulated)`) },
  toggleOffline: () => { const o = !get().offline; set({ offline: o }); get().addEvent(o ? 'warning' : 'info', 'connection', o ? 'Earth link lost, local operation (simulated)' : 'Earth link restored (simulated)') },
  togglePause: () => set((s) => ({ paused: !s.paused })),
  selectRegion: (region) => set({ region }),
  clearLog: () => { saveLog([]); set({ log: [] }) },
  tick: () => {
    const { scenario, history, alerts, paused } = get(); if (paused) return
    const tgt = TARGETS[scenario], last = history[history.length - 1] || {}
    const mix = (k, a) => tgt == null ? null : Math.round((((last[k] == null ? tgt[k] : last[k] + (tgt[k] - last[k]) * 0.25)) + (Math.random() - 0.5) * a) * 10) / 10
    const p = { t: Date.now(), hr: mix('hr', 3), spo2: mix('spo2', 0.6), temp: mix('temp', 0.08), rr: mix('rr', 1.2) }
    if (p.spo2 != null) p.spo2 = Math.min(100, p.spo2)
    const next = { history: [...history, p].slice(-120) }
    const active = alerts.find((a) => a.active)
    if (p.hr != null && p.hr > 120 && !active) {
      const a = { id: crypto.randomUUID(), ts: new Date().toISOString(), active: true, title: 'Elevated heart-rate trend', detail: `HR ${Math.round(p.hr)} BPM above review threshold (120). Sensor-observed; simulated.` }
      next.alerts = [a, ...alerts]; next.region = 'chest'; get().addEvent('critical', 'alert', a.title)
    } else if (active && (p.hr == null || p.hr < 100)) {
      next.alerts = alerts.map((a) => (a.active ? { ...a, active: false } : a)); get().addEvent('info', 'alert', 'Alert cleared, readings back in range')
    }
    set(next)
  },
}))
