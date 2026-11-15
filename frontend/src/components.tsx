import { useState } from 'react'
import type { ReactNode } from 'react'

export const fmt = (n: number | null | undefined, digits = 2) => n == null ? '-' : n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
export const signed = (n: number | null | undefined) => n == null ? '-' : `${n > 0 ? '+' : ''}${fmt(n)}`
export type Column<T> = { key: string; label: string; title?: string; value: (row: T) => string | number | null; render?: (row: T) => ReactNode }

export function DataTable<T>({ rows, columns, rowKey, initialSort, initialDesc = false, caption, scrollRows, allRows = false }: {
  rows: T[]; columns: Column<T>[]; rowKey: (row: T) => string; initialSort?: string; initialDesc?: boolean; caption: string; scrollRows?: number; allRows?: boolean
}) {
  const [sort, setSort] = useState({ key: initialSort ?? columns[0].key, asc: !initialDesc })
  const [page, setPage] = useState(0)
  const column = columns.find(c => c.key === sort.key) ?? columns[0]
  const sorted = [...rows].sort((a, b) => {
    const av = column.value(a), bv = column.value(b)
    if (av == null) return bv == null ? 0 : 1
    if (bv == null) return -1
    const result = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv))
    return result * (sort.asc ? 1 : -1)
  })
  const pageCount = scrollRows || allRows ? 1 : Math.max(1, Math.ceil(sorted.length / 25))
  const current = Math.min(page, pageCount - 1)
  const visible = scrollRows || allRows ? sorted : sorted.slice(current * 25, (current + 1) * 25)
  return <div><div className={`table-wrap${scrollRows ? ' table-scroll' : ''}`} style={scrollRows ? { maxHeight: `var(--table-max-height, ${38 + scrollRows * 52}px)` } : undefined} tabIndex={scrollRows ? 0 : undefined} role={scrollRows ? 'region' : undefined} aria-label={scrollRows ? caption : undefined}><table><caption className={scrollRows || allRows ? 'sr-only' : undefined}>{caption}</caption><thead><tr>{columns.map(c => <th key={c.key} data-column={c.key}
    aria-sort={sort.key === c.key ? sort.asc ? 'ascending' : 'descending' : 'none'}><button title={c.title} onClick={() => { setSort({ key: c.key, asc: sort.key === c.key ? !sort.asc : true }); setPage(0) }}>
      {c.label.toUpperCase()}<span aria-hidden="true">{sort.key === c.key ? sort.asc ? ' ↑' : ' ↓' : ' ↕'}</span></button></th>)}</tr></thead>
    <tbody>{visible.map(row => <tr key={rowKey(row)}>{columns.map(c => <td key={c.key} data-column={c.key}>{c.render ? c.render(row) : columnText(c.value(row))}</td>)}</tr>)}</tbody></table>
    {!rows.length && <p className="empty">NO MATCHING RESULTS IN THE LOADED DATA.</p>}</div>{pageCount > 1 && <div className="table-pagination"><button disabled={current === 0} onClick={() => setPage(current - 1)}>Previous</button><span>{current * 25 + 1}–{Math.min((current + 1) * 25, sorted.length)} of {sorted.length}</span><button disabled={current === pageCount - 1} onClick={() => setPage(current + 1)}>Next</button></div>}</div>
}
const columnText = (value: string | number | null) => value ?? '-'

export function Panel({ title, children, className = '', aside }: { title: string; children: ReactNode; className?: string; aside?: ReactNode }) {
  return <section className={`panel ${className}`}><div className="panel-heading"><h2>{title}</h2>{aside}</div>{children}</section>
}

export function Notice({ children }: { children: ReactNode }) { return <p className="notice">{children}</p> }
