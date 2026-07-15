import { clsx } from 'clsx'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'success' | 'warning' | 'error' | 'accent' | 'muted'
  dot?: boolean
  className?: string
}

export function Badge({ children, variant = 'default', dot, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
        {
          'bg-white/6 text-text-secondary': variant === 'default',
          'bg-emerald-500/15 text-emerald-400': variant === 'success',
          'bg-amber-500/15 text-amber-400': variant === 'warning',
          'bg-red-500/15 text-red-400': variant === 'error',
          'bg-accent/15 text-accent': variant === 'accent',
          'bg-white/4 text-text-muted': variant === 'muted',
        },
        className
      )}
    >
      {dot && (
        <span
          className={clsx('h-1.5 w-1.5 rounded-full', {
            'bg-text-secondary': variant === 'default',
            'bg-emerald-400': variant === 'success',
            'bg-amber-400': variant === 'warning',
            'bg-red-400': variant === 'error',
            'bg-accent': variant === 'accent',
            'bg-text-muted': variant === 'muted',
          })}
        />
      )}
      {children}
    </span>
  )
}
