import { useEffect, type ReactNode } from 'react'
import { BookOpen, CheckCircle2, Trash2, TriangleAlert, X } from 'lucide-react'

export type Toast = { kind: 'error' | 'success'; text: string }

export function ToastBar({ toast, onClose }: { toast: Toast | null; onClose: () => void }) {
  useEffect(() => {
    if (!toast || toast.kind === 'error') return // errors stay until dismissed
    const t = setTimeout(onClose, 6000)
    return () => clearTimeout(t)
  }, [toast, onClose])
  if (!toast) return null
  return (
    <div className={`toast ${toast.kind}`} role={toast.kind === 'error' ? 'alert' : 'status'}>
      {toast.kind === 'error' ? <TriangleAlert size={22} /> : <CheckCircle2 size={22} />}
      <span>{toast.text}</span>
      <button onClick={onClose} aria-label="Dismiss message"><X size={20} /></button>
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </div>
  )
}

export function StatCard({ label, value, note, tone, loading }: {
  label: string; value: string; note: string; tone: 'sand' | 'sage' | 'rose'; loading?: boolean
}) {
  return (
    <div className={`stat-card ${tone}`}>
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{loading ? <span className="skeleton" style={{ width: '60%', height: 34 }} /> : value}</strong>
      <span className="stat-note">{note}</span>
    </div>
  )
}

export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="skeleton-rows" aria-busy="true">
      {Array.from({ length: rows }, (_, i) => <span key={i} className="skeleton" />)}
    </div>
  )
}

export function EmptyState({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <BookOpen size={32} />
      <strong>{title}</strong>
      <p>{text}</p>
      {action}
    </div>
  )
}

export function Avatar({ name, index = 0 }: { name: string; index?: number }) {
  return <span className={`avatar tone-${index % 5}`} aria-hidden="true">{name.trim().charAt(0)}</span>
}

/** Explicit confirmation before deleting a customer. Says exactly what will disappear. */
export function DeleteCustomerConfirm({ name, balance, entries, busy, onConfirm, onCancel }: {
  name: string; balance: number; entries?: number; busy: boolean; onConfirm: () => void; onCancel: () => void
}) {
  return (
    <div className="panel danger-slip" role="alertdialog" aria-label={`Delete ${name}?`}>
      <TriangleAlert size={26} />
      <div>
        <h2>Delete {name}?</h2>
        <p>
          This removes the customer{entries != null ? ` and their ${entries} ${entries === 1 ? 'entry' : 'entries'}` : ' and all their entries'}.
          {balance > 0 && <> The <strong>₹{balance.toLocaleString('en-IN')}</strong> they owe will no longer count in your totals.</>}
        </p>
        <p className="muted">Pages you already confirmed and the corrections they produced are kept. This cannot be undone.</p>
        <div className="header-actions">
          <button className="btn danger" onClick={onConfirm} disabled={busy}><Trash2 size={20} /> {busy ? 'Deleting…' : 'Delete customer'}</button>
          <button className="btn" onClick={onCancel} disabled={busy}>Keep customer</button>
        </div>
      </div>
    </div>
  )
}
