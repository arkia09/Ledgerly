import { ArrowRight, Clock3, FilePlus2, Users, Wallet } from 'lucide-react'
import { dateLabel, money } from '../api'
import type { BalanceReport, Customer } from '../api'
import { Avatar, EmptyState, PageHeader, Skeleton, StatCard } from '../components/ui'

type Props = {
  customers: Customer[]
  report: BalanceReport | null
  loading: boolean
  onOpenCustomer: (id: number) => void
  onGo: (view: 'customers' | 'upload' | 'reports') => void
}

export default function Overview({ customers, report, loading, onOpenCustomer, onGo }: Props) {
  const owing = customers.filter(c => c.balance > 0)
  const overdue = owing.filter(c => (c.oldest_unpaid_days ?? 0) > 30)
  return (
    <>
      <PageHeader
        title="Your khata at a glance"
        subtitle="Who owes you, and for how long."
        actions={<button className="btn primary" onClick={() => onGo('upload')}><FilePlus2 size={22} /> Add a khata page</button>}
      />
      <div className="stat-grid">
        <StatCard label="Total outstanding" value={money(report?.total_outstanding)} note="Owed to you right now" tone="sand" loading={loading} />
        <StatCard label="Customers with dues" value={String(owing.length)} note="Balance above zero" tone="sage" loading={loading} />
        <StatCard label="Needs a reminder" value={String(overdue.length)} note="Unpaid for over 30 days" tone="rose" loading={loading} />
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>Who owes you</h2>
          <button className="link" onClick={() => onGo('customers')}>All customers <ArrowRight size={18} /></button>
        </div>
        {loading ? <Skeleton /> : owing.length === 0 ? (
          <EmptyState title="Nobody owes you anything" text="Upload a khata page or add a sale to see balances here."
            action={<button className="btn primary" onClick={() => onGo('upload')}>Add a khata page</button>} />
        ) : (
          <ul className="list">
            {owing.slice(0, 8).map((c, i) => (
              <li key={c.id}>
                <button className="list-row" onClick={() => onOpenCustomer(c.id)}>
                  <Avatar name={c.name} index={i} />
                  <span className="list-main">
                    <strong>{c.name}</strong>
                    <small>Last activity {dateLabel(c.last_activity, 'unknown')}</small>
                  </span>
                  {(c.oldest_unpaid_days ?? 0) > 30 && (
                    <span className="chip warn"><Clock3 size={16} /> {c.oldest_unpaid_days} days</span>
                  )}
                  <strong className="amount">{money(c.balance)}</strong>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="quick-row">
        <button className="quick" onClick={() => onGo('customers')}><Users size={26} /><span><strong>Find a customer</strong><small>Balances and history</small></span></button>
        <button className="quick" onClick={() => onGo('reports')}><Wallet size={26} /><span><strong>See reports</strong><small>Aging and top dues</small></span></button>
      </div>
    </>
  )
}
