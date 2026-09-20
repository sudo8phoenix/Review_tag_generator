import { StatusBadge } from './StatusBadge'

type Sentiment = 'positive' | 'neutral' | 'negative'

export function SentimentBadge({ sentiment }: { sentiment: Sentiment }) {
  const tone = { positive: 'success', neutral: 'neutral', negative: 'error' } as const
  return <StatusBadge tone={tone[sentiment]}>{sentiment}</StatusBadge>
}
