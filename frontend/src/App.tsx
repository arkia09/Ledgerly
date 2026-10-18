import { useCallback, useEffect, useState } from 'react'
import { CircleHelp, Home, Menu, BarChart3, Upload as UploadIcon, Users, X } from 'lucide-react'
import { errorMessage, post, request } from './api'
import type { AgingReport, BalanceReport, Customer, PagePayload, ReviewRow } from './api'
import { ToastBar, type Toast } from './components/ui'
import CustomerDetail from './views/CustomerDetail'
import Customers from './views/Customers'
import Guide from './views/Guide'
import Overview from './views/Overview'
import Reports from './views/Reports'
import Review from './views/Review'
import Upload from './views/Upload'

type View = 'overview' | 'customers' | 'customer' | 'upload' | 'review' | 'reports' | 'guide'

const NAV = [
  { view: 'overview', label: 'Home', icon: Home },
  { view: 'customers', label: 'Customers', icon: Users },
  { view: 'upload', label: 'Add page', icon: UploadIcon },
  { view: 'reports', label: 'Reports', icon: BarChart3 },
  { view: 'guide', label: 'Help', icon: CircleHelp },
] as const

type ReviewState = { pageId: number; imageUrl: string | null; seconds: number | null; rows: ReviewRow[]; hints: string[] }

export default function App() {
  const [view, setView] = useState<View>('overview')
  const [customerId, setCustomerId] = useState<number | null>(null)
  const [menu, setMenu] = useState(false)
  const [toast, setToast] = useState<Toast | null>(null)
  const [busy, setBusy] = useState(false)

  const [customers, setCustomers] = useState<Customer[]>([])
  const [balances, setBalances] = useState<BalanceReport | null>(null)
  const [aging, setAging] = useState<AgingReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [review, setReview] = useState<ReviewState | null>(null)

  const notify = useCallback((kind: Toast['kind'], text: string) => setToast({ kind, text }), [])
  const closeToast = useCallback(() => setToast(null), [])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [c, b, a] = await Promise.all([
        request<Customer[]>('/customers/'), request<BalanceReport>('/reports/balances/'), request<AgingReport>('/reports/aging/')])
      setCustomers(c); setBalances(b); setAging(a)
    } catch (e) {
      notify('error', errorMessage(e, 'Could not reach the Ledgerly server. Is the backend running?'))
    } finally { setLoading(false) }
  }, [notify])
  useEffect(() => { void refresh() }, [refresh])

  const go = (v: View) => { setView(v); setMenu(false); setToast(null); window.scrollTo(0, 0) }
  const openCustomer = (id: number) => { setCustomerId(id); go('customer') }

  const readPage = async (file: File) => {
    setBusy(true); setToast(null)
    try {
      const form = new FormData(); form.append('image', file)
      const p = await request<PagePayload>('/pages/', { method: 'POST', body: form })
      const general = p.suggestions.filter(s => s.row_index == null).map(s => s.message)
      setReview({
        pageId: p.page_id, imageUrl: p.image_url, seconds: p.seconds, hints: general,
        rows: p.rows.map(r => ({
          uid: r.row_index, row_index: r.row_index, date_text: r.date ?? '', name: r.name ?? '', item: r.item ?? '',
          amount: r.amount == null ? '' : String(r.amount), type: r.type, struck_out: r.struck_out,
          customer_id: r.suggested_customer && r.suggested_customer.score >= 100 ? r.suggested_customer.id : null,
          suggested: r.suggested_customer,
          hints: p.suggestions.filter(s => s.row_index === r.row_index).map(s => s.message),
        })),
      })
      go('review')
    } catch (e) { notify('error', errorMessage(e, 'Could not read that page')) } finally { setBusy(false) }
  }

  const confirm = async () => {
    if (!review) return
    setBusy(true)
    try {
      const rows = review.rows.map(r => ({
        row_index: r.row_index, date_text: r.date_text, name: r.name.trim(), item: r.item.trim() || null,
        amount: Number(r.amount), type: r.type, struck_out: r.struck_out,
        customer_id: r.customer_id, create_new_customer: r.customer_id == null,
      }))
      const res = await post<{ entries_created: number; corrections_created: number }>(`/pages/${review.pageId}/confirm/`, { rows })
      setReview(null); await refresh(); go('overview')
      notify('success', `Saved ${res.entries_created} entries. ${res.corrections_created} corrections will help the next page.`)
    } catch (e) { notify('error', errorMessage(e, 'Could not save this page')) } finally { setBusy(false) }
  }

  const active = view === 'customer' ? 'customers' : view === 'review' ? 'upload' : view

  return (
    <div className="shell">
      <aside className={`sidebar ${menu ? 'open' : ''}`}>
        <div className="cover-inner">
          <div className="brand">
            <div className="plate"><b>Ledgerly</b><span>खाता बही</span></div>
            <button className="icon-btn close" onClick={() => setMenu(false)} aria-label="Close menu"><X size={24} /></button>
          </div>
          <nav>
            {NAV.map(n => (
              <button key={n.view} className={active === n.view ? 'active' : ''} onClick={() => go(n.view)}>
                <n.icon size={24} /> {n.label}
                {n.view === 'customers' && customers.length > 0 && <small>{customers.length}</small>}
              </button>
            ))}
          </nav>
          <p className="side-note">Runs on this computer. Your records stay here.</p>
        </div>
      </aside>
      {menu && <div className="scrim" onClick={() => setMenu(false)} />}

      <main>
        <header className="topbar">
          <button className="icon-btn" onClick={() => setMenu(true)} aria-label="Open menu"><Menu size={26} /></button>
          <span className="brand-sm">Ledgerly</span>
        </header>
        <ToastBar toast={toast} onClose={closeToast} />
        <div className="content">
          {view === 'overview' && <Overview customers={customers} report={balances} loading={loading} onOpenCustomer={openCustomer} onGo={go} />}
          {view === 'customers' && <Customers customers={customers} loading={loading} onOpenCustomer={openCustomer} onUpload={() => go('upload')} onChanged={refresh} notify={notify} />}
          {view === 'customer' && customerId != null && <CustomerDetail id={customerId} onBack={() => go('customers')} onChanged={refresh} notify={notify} />}
          {view === 'upload' && <Upload busy={busy} onRead={f => void readPage(f)} />}
          {view === 'review' && review && (
            <Review imageUrl={review.imageUrl} rows={review.rows} generalHints={review.hints} seconds={review.seconds}
              customers={customers} busy={busy} onChange={rows => setReview({ ...review, rows })}
              onConfirm={() => void confirm()} onCancel={() => { setReview(null); go('upload') }} />
          )}
          {view === 'reports' && <Reports balances={balances} aging={aging} loading={loading} onRefresh={() => void refresh()} onOpenCustomer={openCustomer} />}
          {view === 'guide' && <Guide />}
        </div>
      </main>
    </div>
  )
}
