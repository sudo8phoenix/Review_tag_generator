import type { ReactNode } from 'react'

type Column = { key: string; label: string }
type Props = {
  caption: string
  columns: Column[]
  rows: Record<string, ReactNode>[]
  emptyMessage?: string
}

export function DataTable({ caption, columns, rows, emptyMessage = 'No rows available.' }: Props) {
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label={`${caption} table, scrollable`}>
      <table>
        <caption>{caption}</caption>
        <thead><tr>{columns.map((column) => <th key={column.key} scope="col">{column.label}</th>)}</tr></thead>
        <tbody>
          {rows.length === 0
            ? <tr><td colSpan={columns.length}>{emptyMessage}</td></tr>
            : rows.map((row, index) => (
              <tr key={index}>{columns.map((column) => <td key={column.key}>{row[column.key]}</td>)}</tr>
            ))}
        </tbody>
      </table>
    </div>
  )
}
