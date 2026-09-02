import { useCallback } from 'react'
import './RangeSlider.css'

interface Props {
  min: number
  max: number
  step?: number
  value: [number, number]
  onChange: (value: [number, number]) => void
  /** Minimum distance kept between the two thumbs. */
  minGap?: number
  /** Render the value bubbles / bounds (e.g. n => `${n} yr`). */
  format?: (n: number) => string
}

/**
 * Dual-thumb range slider — the user drags two handles to bound a range.
 * Built from two overlaid <input type="range"> elements; only the thumbs are
 * interactive (the inputs themselves are pointer-events:none).
 */
export default function RangeSlider({
  min,
  max,
  step = 1,
  value,
  onChange,
  minGap = 0,
  format = String,
}: Props) {
  const [lo, hi] = value
  const span = max - min || 1
  const loPct = ((lo - min) / span) * 100
  const hiPct = ((hi - min) / span) * 100

  const handleLo = useCallback(
    (n: number) => onChange([Math.min(n, hi - minGap), hi]),
    [hi, minGap, onChange],
  )
  const handleHi = useCallback(
    (n: number) => onChange([lo, Math.max(n, lo + minGap)]),
    [lo, minGap, onChange],
  )

  return (
    <div className="range-slider">
      <div className="rs-rail" />
      <div className="rs-fill" style={{ left: `${loPct}%`, right: `${100 - hiPct}%` }} />

      <input
        type="range"
        className="rs-input"
        // keep the lower thumb reachable when both sit at the far right
        style={{ zIndex: lo > max - (max - min) / 10 ? 5 : undefined }}
        min={min}
        max={max}
        step={step}
        value={lo}
        aria-label="Minimum"
        onChange={e => handleLo(Number(e.target.value))}
      />
      <input
        type="range"
        className="rs-input"
        min={min}
        max={max}
        step={step}
        value={hi}
        aria-label="Maximum"
        onChange={e => handleHi(Number(e.target.value))}
      />

      <div className="rs-bounds">
        <span>{format(lo)}</span>
        <span>{format(hi)}</span>
      </div>
    </div>
  )
}
