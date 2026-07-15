import { useState, useRef } from 'react'
import { clsx } from 'clsx'

interface TooltipProps {
  content: string
  children: React.ReactNode
  side?: 'top' | 'right' | 'bottom' | 'left'
  delay?: number
}

export function Tooltip({ content, children, side = 'top', delay = 300 }: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>()

  const show = () => { timer.current = setTimeout(() => setVisible(true), delay) }
  const hide = () => { clearTimeout(timer.current); setVisible(false) }

  return (
    <div className="relative inline-flex" onMouseEnter={show} onMouseLeave={hide}>
      {children}
      {visible && (
        <div
          className={clsx(
            'pointer-events-none absolute z-50 whitespace-nowrap rounded-md bg-surface-4 border border-border-subtle px-2 py-1 text-xs text-text-primary shadow-lg animate-fade-in',
            {
              'bottom-full mb-2 left-1/2 -translate-x-1/2': side === 'top',
              'top-full mt-2 left-1/2 -translate-x-1/2': side === 'bottom',
              'right-full mr-2 top-1/2 -translate-y-1/2': side === 'left',
              'left-full ml-2 top-1/2 -translate-y-1/2': side === 'right',
            }
          )}
        >
          {content}
        </div>
      )}
    </div>
  )
}
