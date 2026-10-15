import { describe, expect, it } from 'vitest'
import { sourceSelection } from './annotationSpans'

describe('source selection offsets', () => {
  it('counts emoji as source code points rather than UTF-16 units', () => {
    const text = '😀 Great wifi.'
    const start = text.indexOf('wifi')
    expect(sourceSelection(text, start, start + 4)).toEqual({ start: 8, end: 12 })
  })
  it('retains original CRLF positions after textarea newline normalization', () => {
    const text = '😀\r\nGood wifi\rservice.'
    const displayed = text.replace(/\r\n?/g, '\n')
    const start = displayed.indexOf('service')
    expect(sourceSelection(text, start, start + 7)).toEqual({ start: 13, end: 20 })
    const wifi = displayed.indexOf('wifi')
    expect(sourceSelection(text, wifi, wifi + 4)).toEqual({ start: 8, end: 12 })
  })
  it('trims selected whitespace and ignores empty selections', () => {
    expect(sourceSelection('  wifi  ', 0, 8)).toEqual({ start: 2, end: 6 })
    expect(sourceSelection('   ', 0, 3)).toBeNull()
    expect(sourceSelection('wifi', 2, 2)).toBeNull()
  })
  it('expands an interior surrogate selection to the full source character', () => {
    expect(sourceSelection('😀 wifi', 1, 2)).toEqual({ start: 0, end: 1 })
  })
})
