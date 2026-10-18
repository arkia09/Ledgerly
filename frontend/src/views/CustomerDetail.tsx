import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ArrowLeft, Banknote, ShoppingBag, Trash2 } from 'lucide-react'
import { dateLabel, errorMessage, money, post, request, todayISO } from '../api'
import type { CustomerDetail as Detail } from '../api'
import { DeleteCustomerConfirm, PageHeader, Skeleton, StatCard } from '../components/ui'

type Props = {
  id: number
  onBack: () => void
  onChanged: () => Promise<void>
  notify: (kind: 'error' | 'success', text: string) => void
}

export default function CustomerDetail({ id, onBack, onChanged, notify }: Props) {
  const [detail, setDetail] = useState<Detail | null>(null)
  const [mode, setMode] = useState<'sale' | 'payment' | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  const [date, setDate] = useState(todayISO())
  const [item, setItem] = useState('')
  const [total, setTotal] = useState('')
  const [paid, setPaid] = useState('0')
  const [amount, setAmount] = useState('')

  const load = useCallback(async () => {
    try { setDetail(await request<Detail>(`/customers/${id}/`)) }
    catch (e) { notify('error', errorMessage(e, 'Could not load customer')) }
  }, [id, notify])
  useEffect(() => { void load() }, [load])

  const done = async (message: string) => {
    notify('success', message)
    setMode(null); setItem(''); setTotal(''); setPaid('0'); setAmount('')
    await Promise.all([load(), onChanged()])
  }

  const saveSale = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true)
    try {
      const r = await post<{ paid_amount: number; remaining_due: number }>(`/customers/${id}/sales/`,
        { item, total_amount: total, paid_amount: paid, date_text: date })
      await done(`Sale saved. ${money(r.paid_amount)} paid, ${money(r.remaining_due)} still due.`)
    } catch (err) { notify('error', errorMessage(err, 'Could not save sale')) } finally { setBusy(false) }
  }

  const savePayment = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true)
    try {
      await post(`/customers/${id}/payments/`, { amount, date_text: date })
      await done(`Payment of ${money(amount)} saved.`)
    } catch (err) { notify('error', errorMessage(err, 'Could not save payment')) } finally { setBusy(false) }
  }

  const remove = async () => {
    if (!detail) return
    setBusy(true)
    try {
      const r = await post<{ entries_deleted: number }>(`/customers/${id}/delete/`, {})
      await onChanged()
      onBack()
      notify('success', `${detail.name} deleted along with ${r.entries_deleted} ${r.entries_deleted === 1 ? 'entry' : 'entries'}.`)
    } catch (err) { notify('error', errorMessage(err, 'Could not delete customer')); setBusy(false) }
  }

  if (!detail) return <><button className="back" onClick={onBack}><ArrowLeft size={20} /> All customers</button><Skeleton /></>

  const due = Math.max(0, Number(total || 0) - Number(paid || 0))
  const saleValid = Number(total) > 0 && Number(paid) >= 0 && Number(paid) <= Number(total)

  return (
    <>
      <button className="back" onClick={onBack}><ArrowLeft size={20} /> All customers</button>
      <PageHeader title={detail.name} subtitle={`Last activity ${dateLabel(detail.last_activity, 'none yet')}`}
        actions={<>
          <button className={`btn ${mode === 'sale' ? 'primary' : ''}`} onClick={() => setMode(mode === 'sale' ? null : 'sale')}><ShoppingBag size={22} /> Record sale</button>
          <button className={`btn ${mode === 'payment' ? 'primary' : ''}`} onClick={() => setMode(mode === 'payment' ? null : 'payment')}><Banknote size={22} /> Record payment</button>
          <button className="btn danger-outline" onClick={() => { setMode(null); setConfirmDelete(true) }}><Trash2 size={22} /> Delete</button>
        </>} />

      {confirmDelete && <DeleteCustomerConfirm name={detail.name} balance={detail.balance} entries={detail.entries.length} busy={busy}
        onConfirm={() => void remove()} onCancel={() => setConfirmDelete(false)} />}

      <div className="stat-grid">
        <StatCard label="Balance due" value={money(detail.balance)} note="Credit minus payments" tone="sand" />
        <StatCard label="Entries" value={String(detail.entries.length)} note="Sales and payments" tone="sage" />
        <StatCard label="Oldest unpaid" value={detail.oldest_unpaid_days == null ? '—' : `${detail.oldest_unpaid_days} days`} note="Oldest credit still open" tone="rose" />
      </div>

      {mode === 'sale' && (
        <form className="panel form-grid" onSubmit={e => void saveSale(e)}>
          <h2>Record a sale</h2>
          <label>What was sold<input value={item} maxLength={200} onChange={e => setItem(e.target.value)} placeholder="e.g. Rice, oil" /></label>
          <label>Date<input type="date" required value={date} onChange={e => setDate(e.target.value)} /></label>
          <label>Total (₹)<input type="number" inputMode="decimal" min="0.01" step="0.01" required value={total} onChange={e => setTotal(e.target.value)} placeholder="500" /></label>
          <label>Paid now (₹)<input type="number" inputMode="decimal" min="0" step="0.01" required value={paid} onChange={e => setPaid(e.target.value)} /></label>
          <div className="preview">Still due <strong>{money(due)}</strong>
            <span>{Number(total) > 0 && Number(paid) >= Number(total) ? 'Paid in full' : Number(paid) > 0 ? 'Part paid' : 'On credit'}</span></div>
          <button className="btn primary" disabled={busy || !saleValid}>{busy ? 'Saving…' : 'Save sale'}</button>
        </form>
      )}

      {mode === 'payment' && (
        <form className="panel form-grid" onSubmit={e => void savePayment(e)}>
          <h2>Record a payment</h2>
          <label>Date<input type="date" required value={date} onChange={e => setDate(e.target.value)} /></label>
          <label>Amount received (₹)<input autoFocus type="number" inputMode="decimal" min="0.01" step="0.01" required value={amount} onChange={e => setAmount(e.target.value)} placeholder="100" /></label>
          {detail.balance > 0 && <button type="button" className="btn" onClick={() => setAmount(String(detail.balance))}>Fill full balance ({money(detail.balance)})</button>}
          <button className="btn primary" disabled={busy || !(Number(amount) > 0)}>{busy ? 'Saving…' : 'Save payment'}</button>
        </form>
      )}

      <section className="panel">
        <div className="panel-head"><h2>History</h2></div>
        {detail.entries.length === 0 ? <p className="muted pad">No entries yet. Record a sale to begin.</p> : (
          <div className="table-scroll">
            <table className="table">
              <thead><tr><th>Date</th><th>Details</th><th>Type</th><th className="num">Amount</th><th className="num">Balance</th></tr></thead>
              <tbody>
                {detail.entries.map(e => (
                  <tr key={e.id} className={e.struck_out ? 'struck' : ''}>
                    <td>{e.date ? dateLabel(e.date) : e.date_text || 'Unknown'}</td>
                    <td>{e.item || 'Ledger entry'}{e.struck_out && <span className="chip">Voided</span>}</td>
                    <td><span className={`chip ${e.type}`}>{e.type === 'credit' ? 'Credit' : 'Payment'}</span></td>
                    <td className={`num strong ${e.type}`}>{e.type === 'payment' ? '−' : '+'}{money(e.amount)}</td>
                    <td className="num strong">{money(e.running_balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
