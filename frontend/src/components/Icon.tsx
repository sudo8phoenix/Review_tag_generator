type Name = 'bookmark' | 'compare' | 'browser' | 'grid' | 'search' | 'arrow' | 'plus' | 'check' | 'quote' | 'sliders' | 'spark'

const paths: Record<Name, string> = {
  bookmark: 'M6 4h12v17l-6-4-6 4V4Z',
  compare: 'M8 3v18M16 3v18M4 8h8M12 16h8',
  browser: 'M3 5h18v15H3V5ZM3 10h18M7 7.5h.01M10 7.5h.01',
  grid: 'M4 4h6v6H4V4ZM14 4h6v6h-6V4ZM4 14h6v6H4v-6ZM14 14h6v6h-6v-6Z',
  search: 'm20 20-5-5M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  plus: 'M12 5v14M5 12h14',
  check: 'm5 12 4 4L19 6',
  quote: 'M5 7h6v6H6c0 3 2 4 4 4M15 7h6v6h-5c0 3 2 4 4 4',
  sliders: 'M4 7h7m5 0h4M4 17h3m5 0h8M11 4v6M7 14v6',
  spark: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',
}

export function Icon({ name, className = '' }: { name: Name; className?: string }) {
  return <svg className={`icon ${className}`} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
