import { forwardRef } from 'react'
import { clsx } from 'clsx'

interface ScrollAreaProps {
  children: React.ReactNode
  className?: string
}

export const ScrollArea = forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ children, className }, ref) => (
    <div
      ref={ref}
      className={clsx(
        'overflow-y-auto scrollbar-thin scrollbar-thumb-border-default scrollbar-track-transparent',
        className
      )}
    >
      {children}
    </div>
  )
)
ScrollArea.displayName = 'ScrollArea'
