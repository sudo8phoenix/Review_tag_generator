/** Map a textarea selection back to exact source code points, including CRLF. */
export function sourceSelection(text: string, selectionStart: number, selectionEnd: number): { start: number; end: number } | null {
  if (selectionStart >= selectionEnd) return null
  const chars = Array.from(text)
  let displayedUnits = 0
  let start: number | null = null
  let end = 0
  for (let index = 0; index < chars.length; index++) {
    const character = chars[index] ?? ''
    const sourceStart = index
    // Textarea values normalize both CRLF and CR to a single LF.
    if (character === '\r' && chars[index + 1] === '\n') index++
    const length = character === '\r' ? 1 : character.length
    if (displayedUnits + length > selectionStart && displayedUnits < selectionEnd) {
      if (start === null) start = sourceStart
      end = index + 1
    }
    displayedUnits += length
  }
  if (start === null) return null
  while (start < end && /\s/.test(chars[start] ?? '')) start++
  while (end > start && /\s/.test(chars[end - 1] ?? '')) end--
  return end > start ? { start, end } : null
}
