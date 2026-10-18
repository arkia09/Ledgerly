export type Customer = {
  id: number
  name: string
  balance: number
  last_activity: string | null
  oldest_unpaid_days: number | null
}

export type Entry = {
  id: number
  date: string | null
  date_text: string
  item: string | null
  amount: number
  type: 'credit' | 'payment'
  struck_out: boolean
  running_balance: number
}

export type CustomerDetail = Customer & { entries: Entry[] }

export type RowType = 'credit' | 'payment' | 'unknown'

/** One extracted row as the review screen edits it. */
export type ReviewRow = {
  uid: number
  row_index: number | null // null = row added by the user
  date_text: string
  name: string
  item: string
  amount: string
  type: RowType
  struck_out: boolean
  customer_id: number | null // null = create / reuse by exact name
  suggested: { id: number; name: string; score: number } | null
  hints: string[]
}

export type PagePayload = {
  page_id: number
  image_url: string | null
  seconds: number | null
  model?: string
  rows: {
    row_index: number
    date: string | null
    name: string | null
    item: string | null
    amount: number | null
    type: RowType
    struck_out: boolean
    suggested_customer: { id: number; name: string; score: number } | null
  }[]
  suggestions: { row_index: number | null; message: string }[]
}

export type BalanceReport = {
  total_outstanding: number
  customers: { id: number; name: string; balance: number; last_activity: string | null }[]
}

export type AgingReport = {
  buckets: Record<'0-30' | '31-60' | '61+' | 'unknown', number>
  customers: ({ id: number; name: string; total: number } & Record<string, number | string>)[]
}

const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.message || data.error || `Request failed (${res.status})`)
  return data as T
}

export const post = <T,>(path: string, body: unknown) =>
  request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
export const money = (n: number | string | null | undefined) => inr.format(Number(n || 0))

export const dateLabel = (d: string | null | undefined, fallback = 'No activity yet') =>
  d
    ? new Date(`${d}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : fallback

export const errorMessage = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback)

export const todayISO = () => new Date().toISOString().slice(0, 10)
