import { useState } from 'react'
import { Check, LoaderCircle, Plus, Trash2, TriangleAlert } from 'lucide-react'
import type { Customer, ReviewRow, RowType } from '../api'
import { PageHeader } from '../components/ui'

type Props = {
  imageUrl: string | null
  rows: ReviewRow[]
  generalHints: string[]
  seconds: number | null
  customers: Customer[]
  busy: boolean
  onChange: (rows: ReviewRow[]) => void
  onConfirm: () => void
  onCancel: () => void
}

let nextUid = 100000

export default function Review({ imageUrl, rows, generalHints, seconds, customers, busy, onChange, onConfirm, onCancel }: Props) {
  const [zoom, setZoom] = useState(false)
  const patch = (uid: number, p: Partial<ReviewRow>) => onChange(rows.map(r => (r.uid === uid ? { ...r, ...p } : r)))
  const remove = (uid: number) => onChange(rows.filter(r => r.uid !== uid))
  const add = () => onChange([...rows, { uid: nextUid++, row_index: null, date_text: '', name: '', item: '', amount: '',
    type: 'credit', struck_out: false, customer_id: null, suggested: null, hints: [] }])

  const invalid = (r: ReviewRow) => !r.name.trim() || !(Number(r.amount) > 0) || r.type === 'unknown'
  const problems = rows.filter(invalid).length
  const live = rows.filter(r => !r.struck_out).length

  return (
    <>
      <PageHeader title="Check the entries" subtitle="Compare each card with your photo. Nothing is saved until you confirm."
        actions={<button className="btn" onClick={onCancel} disabled={busy}>Start over</button>} />

      {generalHints.map(h => <div key={h} className="notice"><TriangleAlert size={22} /><span>{h}</span></div>)}

      <div className="review">
        {imageUrl && (
          <aside className="photo">
            <img src={imageUrl} alt="Uploaded ledger page" className={zoom ? 'zoomed' : ''} onClick={() => setZoom(z => !z)} />
            <small>Tap the photo to {zoom ? 'shrink' : 'enlarge'} it</small>
          </aside>
        )}
        <div className="cards">
          {rows.map((r, i) => {
            const matchValue = r.customer_id ?? 'new'
            const bad = invalid(r)
            return (
              <article key={r.uid} className={`row-card ${r.struck_out ? 'struck' : ''} ${bad ? 'bad' : ''}`}>
                <header>
                  <strong>Row {i + 1}</strong>
                  {r.row_index == null && <span className="chip">Added by you</span>}
                  <button className="icon-btn" onClick={() => remove(r.uid)} aria-label={`Remove row ${i + 1}`} title="Remove this row"><Trash2 size={20} /></button>
                </header>
                {r.hints.map(h => <p key={h} className="hint"><TriangleAlert size={18} /> {h}</p>)}
                <div className="fields">
                  <label>Name
                    <input value={r.name} onChange={e => patch(r.uid, { name: e.target.value, customer_id: null })} />
                  </label>
                  <label>Date
                    <input value={r.date_text} placeholder="e.g. 12/10" onChange={e => patch(r.uid, { date_text: e.target.value })} />
                  </label>
                  <label>Item
                    <input value={r.item} placeholder="optional" onChange={e => patch(r.uid, { item: e.target.value })} />
                  </label>
                  <label>Amount (₹)
                    <input type="number" inputMode="decimal" min="0.01" step="0.01" value={r.amount} onChange={e => patch(r.uid, { amount: e.target.value })} />
                  </label>
                </div>
                <div className="row-foot">
                  <div className="segmented" role="group" aria-label={`Type for row ${i + 1}`}>
                    {(['credit', 'payment'] as RowType[]).map(t => (
                      <button key={t} className={r.type === t ? 'on' : ''} onClick={() => patch(r.uid, { type: t })}>
                        {t === 'credit' ? 'Credit (udhaar)' : 'Payment received'}
                      </button>
                    ))}
                  </div>
                  <label className="check"><input type="checkbox" checked={r.struck_out} onChange={e => patch(r.uid, { struck_out: e.target.checked })} /> Crossed out in book</label>
                </div>
                <label className="match">Customer
                  <select value={matchValue} onChange={e => {
                    const v = e.target.value
                    patch(r.uid, v === 'new' ? { customer_id: null }
                      : { customer_id: Number(v), name: customers.find(c => c.id === Number(v))?.name ?? r.name })
                  }}>
                    <option value="new">{r.name.trim() ? `New / same name: ${r.name.trim()}` : 'New customer'}</option>
                    {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  {r.suggested && r.customer_id !== r.suggested.id && (
                    <button className="link" type="button" onClick={() => patch(r.uid, { customer_id: r.suggested!.id, name: r.suggested!.name })}>
                      Looks like {r.suggested.name} ({Math.round(r.suggested.score)}%): use it
                    </button>
                  )}
                </label>
              </article>
            )
          })}
          <button className="btn add-row" onClick={add}><Plus size={22} /> Add a missing row</button>
        </div>
      </div>

      <div className="confirm-bar">
        <span>
          {rows.length} rows{seconds ? ` · read in ${Math.round(seconds)}s` : ''}
          {problems > 0 ? <strong className="bad-text"> · {problems} need fixing</strong> : <> · {live} will count toward balances</>}
        </span>
        <button className="btn primary big" disabled={busy || problems > 0 || rows.length === 0} onClick={onConfirm}>
          {busy ? <><LoaderCircle className="spin" size={22} /> Saving…</> : <><Check size={22} /> Confirm {rows.length} entries</>}
        </button>
      </div>
    </>
  )
}
