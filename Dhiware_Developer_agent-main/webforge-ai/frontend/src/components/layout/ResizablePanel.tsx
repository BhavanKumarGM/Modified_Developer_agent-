import { useRef, useCallback } from 'react'
import { clsx } from 'clsx'

interface ResizablePanelProps {
  children: React.ReactNode
  minWidth?: number
  maxWidth?: number
  width: number
  onResize: (width: number) => void
  side?: 'left' | 'right'
  className?: string
}

export function ResizablePanel({
  children,
  minWidth = 200,
  maxWidth = 800,
  width,
  onResize,
  side = 'right',
  className,
}: ResizablePanelProps) {
  const isDragging = useRef(false)
  const startX = useRef(0)
  const startW = useRef(0)

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      isDragging.current = true
      startX.current = e.clientX
      startW.current = width

      const onMouseMove = (ev: MouseEvent) => {
        if (!isDragging.current) return
        const delta = side === 'right' ? ev.clientX - startX.current : startX.current - ev.clientX
        const newW = Math.max(minWidth, Math.min(maxWidth, startW.current + delta))
        onResize(newW)
      }

      const onMouseUp = () => {
        isDragging.current = false
        document.removeEventListener('mousemove', onMouseMove)
        document.removeEventListener('mouseup', onMouseUp)
        document.body.style.cursor = ''
        document.body.style.userSelect = ''
      }

      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
    },
    [width, minWidth, maxWidth, onResize, side]
  )

  return (
    <div className={clsx('relative flex-shrink-0', className)} style={{ width }}>
      {children}
      <div
        onMouseDown={onMouseDown}
        className={clsx(
          'absolute top-0 bottom-0 w-1 cursor-col-resize z-10 hover:bg-accent/40 transition-colors group',
          side === 'right' ? 'right-0' : 'left-0'
        )}
      />
    </div>
  )
}
