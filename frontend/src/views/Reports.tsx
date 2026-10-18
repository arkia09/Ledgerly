import { RefreshCw } from 'lucide-react'
import { money } from '../api'
import type { AgingReport, BalanceReport } from '../api'
import { AgingBar, BalanceBars, BUCKETS } from '../components/Charts'
import { EmptyState, PageHeader, Skeleton, StatCard } from '../components/ui'

type Props = {
  balances: BalanceReport | null
  aging: AgingReport | null
  loading: boolean
  onRefresh: () => void
  onOpenCustomer: (id: number) => void
}

export default function Reports({ balances, aging, loading, onRefresh, onOpenCustomer }: Props) {
  const old = (aging?.buckets['31-60'] || 0) + (aging?.buckets['61+'] || 0)
  const empty = !loading && (balances?.customers.length ?? 0) === 0
  return (
    <>
      <PageHeader title="Reports" subtitle="Who owes the most, and how long it has been waiting."
        actions={<button className="btn" onClick={onRefresh}><RefreshCw size={20} /> Refresh</button>} />
      <div className="stat-grid">
        <StatCard label="Total outstanding" value={money(balances?.total_outstanding)} note="All customers" tone="sand" loading={loading} />
        <StatCard label="Recent (0–30 days)" value={money(aging?.buckets['0-30'])} note="Still fresh" tone="sage" loading={loading} />
        <StatCard label="Older than 30 days" value={money(old)} note="Worth a reminder" tone="rose" loading={loading} />
      </div>

      {loading ? <Skeleton /> : empty ? (
        <section className="panel"><EmptyState title="Nothing to report yet" text="Balances appear once customers owe money." /></section>
      ) : (
        <>
          <div className="two-col">
            <section className="panel pad">
              <h2>Top dues</h2>
              {balances && <BalanceBars report={balances} />}
            </section>
            <section className="panel pad">
              <h2>How old is the money owed</h2>
              {aging && <AgingBar report={aging} />}
              <p className="muted">Payments are applied to the oldest credit first.</p>
            </section>
          </div>

          <section className="panel">
            <div className="panel-head"><h2>Aging by customer</h2></div>
            <div className="table-scroll">
              <table className="table">
                <thead><tr><th>Customer</th>{BUCKETS.map(b => <th key={b.key} className="num">{b.label}</th>)}<th className="num">Total</th></tr></thead>
                <tbody>
                  {aging?.customers.map(c => (
                    <tr key={c.id} className="click" onClick={() => onOpenCustomer(c.id)}>
                      <td><strong>{c.name}</strong></td>
                      {BUCKETS.map(b => <td key={b.key} className="num">{Number(c[b.key]) ? money(Number(c[b.key])) : '–'}</td>)}
                      <td className="num strong">{money(c.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </>
  )
}
