import { useMemo, useState, type FormEvent } from 'react'
import { FilePlus2, Pencil, Search, Trash2, UserPlus, X } from 'lucide-react'
import { dateLabel, errorMessage, money, post } from '../api'
import type { Customer } from '../api'
import { Avatar, DeleteCustomerConfirm, EmptyState, PageHeader, Skeleton } from '../components/ui'

type Filter = 'all' | 'owing' | 'overdue'
type Props = {
  customers: Customer[]
  loading: boolean
  onOpenCustomer: (id: number) => void
  onUpload: () => void
  onChanged: () => Promise<void>
  notify: (kind: 'error' | 'success', text: string) => void
}

export default function Customers({ customers, loading, onOpenCustomer, onUpload, onChanged, notify }: Props) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [form, setForm] = useState<{ mode: 'add' } | { mode: 'edit'; id: number } | null>(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [deleting, setDeleting] = useState<Customer | null>(null)

  const shown = useMemo(() => {
    const q = query.trim().toLocaleLowerCase()
    return customers.filter(c =>
      c.name.toLocaleLowerCase().includes(q) &&
      (filter === 'all' || (filter === 'owing' ? c.balance > 0 : c.balance > 0 && (c.oldest_unpaid_days ?? 0) > 30)))
  }, [customers, query, filter])

  const open = (f: NonNullable<typeof form>, initial = '') => { setForm(f); setName(initial) }

  const save = async (e: FormEvent) => {
    e.preventDefault()
    if (!form) return
    setBusy(true)
    try {
      if (form.mode === 'add') {
        const c = await post<Customer>('/customers/create/', { name })
        notify('success', `${c.name} added.`)
      } else {
        await post(`/customers/${form.id}/update/`, { name })
        notify('success', 'Name updated.')
      }
      setForm(null)
      await onChanged()
    } catch (err) {
      notify('error', errorMessage(err, 'Could not save customer'))
    } finally { setBusy(false) }
  }

  const remove = async () => {
    if (!deleting) return
    setBusy(true)
    try {
      const r = await post<{ entries_deleted: number }>(`/customers/${deleting.id}/delete/`, {})
      notify('success', `${deleting.name} deleted along with ${r.entries_deleted} ${r.entries_deleted === 1 ? 'entry' : 'entries'}.`)
      setDeleting(null)
      await onChanged()
    } catch (err) {
      notify('error', errorMessage(err, 'Could not delete customer'))
    } finally { setBusy(false) }
  }

  const counts = { all: customers.length, owing: customers.filter(c => c.balance > 0).length,
    overdue: customers.filter(c => c.balance > 0 && (c.oldest_unpaid_days ?? 0) > 30).length }

  return (
    <>
      <PageHeader title="Customers" subtitle="Tap a customer to see their full history."
        actions={<>
          <button className="btn" onClick={() => open({ mode: 'add' })}><UserPlus size={22} /> Add customer</button>
          <button className="btn primary" onClick={onUpload}><FilePlus2 size={22} /> Add khata page</button>
        </>} />

      {form && (
        <form className="panel inline-form" onSubmit={e => void save(e)}>
          <label>{form.mode === 'add' ? 'New customer name' : 'Customer name'}
            <input autoFocus required maxLength={200} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Priya Sharma" />
          </label>
          <button className="btn primary" disabled={busy || !name.trim()}>{busy ? 'Saving…' : 'Save'}</button>
          <button type="button" className="btn" onClick={() => setForm(null)}>Cancel</button>
        </form>
      )}

      {deleting && <DeleteCustomerConfirm name={deleting.name} balance={deleting.balance} busy={busy}
        onConfirm={() => void remove()} onCancel={() => setDeleting(null)} />}

      <section className="panel">
        <div className="toolbar">
          <div className="search">
            <Search size={22} />
            <input placeholder="Search by name" value={query} onChange={e => setQuery(e.target.value)} aria-label="Search customers" />
            {query && <button onClick={() => setQuery('')} aria-label="Clear search"><X size={20} /></button>}
          </div>
          <div className="segmented" role="group" aria-label="Filter customers">
            {([['all', 'All'], ['owing', 'Owes money'], ['overdue', 'Over 30 days']] as const).map(([k, label]) => (
              <button key={k} className={filter === k ? 'on' : ''} onClick={() => setFilter(k)}>{label} <small>{counts[k]}</small></button>
            ))}
          </div>
        </div>

        {loading ? <Skeleton /> : shown.length === 0 ? (
          <EmptyState title="No customers found" text={customers.length ? 'Try a different name or filter.' : 'Add a customer or upload a khata page to get started.'} />
        ) : (
          <ul className="list">
            {shown.map((c, i) => (
              <li key={c.id} className="with-action">
                <button className="list-row" onClick={() => onOpenCustomer(c.id)}>
                  <Avatar name={c.name} index={i} />
                  <span className="list-main">
                    <strong>{c.name}</strong>
                    <small>{c.balance > 0 && c.oldest_unpaid_days != null ? `Oldest unpaid ${c.oldest_unpaid_days} days · ` : ''}Last activity {dateLabel(c.last_activity, 'none')}</small>
                  </span>
                  <strong className={`amount ${c.balance <= 0 ? 'zero' : ''}`}>{money(c.balance)}</strong>
                </button>
                <button className="icon-btn" title={`Rename ${c.name}`} aria-label={`Rename ${c.name}`} onClick={() => { setDeleting(null); open({ mode: 'edit', id: c.id }, c.name) }}><Pencil size={20} /></button>
                <button className="icon-btn danger-icon" title={`Delete ${c.name}`} aria-label={`Delete ${c.name}`} onClick={() => { setForm(null); setDeleting(c) }}><Trash2 size={20} /></button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
