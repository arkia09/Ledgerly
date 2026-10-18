import { money } from '../api'
import type { AgingReport, BalanceReport } from '../api'

export const BUCKETS = [
  { key: '0-30', label: '0–30 days', color: 'var(--green)' },
  { key: '31-60', label: '31–60 days', color: 'var(--amber)' },
  { key: '61+', label: '61+ days', color: 'var(--red)' },
  { key: 'unknown', label: 'No date', color: 'var(--grey)' },
] as const

/** Horizontal bars: top customers by balance. Plain HTML so Devanagari names render correctly. */
export function BalanceBars({ report, limit = 10 }: { report: BalanceReport; limit?: number }) {
  const rows = report.customers.slice(0, limit)
  const max = Math.max(...rows.map(r => r.balance), 1)
  return (
    <ol className="bars">
      {rows.map(r => (
        <li key={r.id}>
          <span className="bar-name">{r.name}</span>
          <span className="bar-track"><span className="bar-fill" style={{ width: `${(r.balance / max) * 100}%` }} /></span>
          <strong>{money(r.balance)}</strong>
        </li>
      ))}
    </ol>
  )
}

/** One stacked bar for the totals plus a legend. */
export function AgingBar({ report }: { report: AgingReport }) {
  const total = BUCKETS.reduce((s, b) => s + (report.buckets[b.key] || 0), 0)
  return (
    <div>
      <div className="stack" role="img" aria-label="Outstanding amount by age">
        {total === 0
          ? <span className="stack-empty" />
          : BUCKETS.map(b => report.buckets[b.key] > 0 && (
              <span key={b.key} style={{ width: `${(report.buckets[b.key] / total) * 100}%`, background: b.color }} />
            ))}
      </div>
      <ul className="legend">
        {BUCKETS.map(b => (
          <li key={b.key}>
            <i style={{ background: b.color }} />
            <span>{b.label}</span>
            <strong>{money(report.buckets[b.key])}</strong>
            <small>{total ? Math.round(((report.buckets[b.key] || 0) / total) * 100) : 0}%</small>
          </li>
        ))}
      </ul>
    </div>
  )
}
