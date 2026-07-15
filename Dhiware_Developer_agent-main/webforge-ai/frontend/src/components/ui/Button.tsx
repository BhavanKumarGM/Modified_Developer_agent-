import { forwardRef } from 'react'
import { clsx } from 'clsx'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'danger' | 'outline'
  size?: 'sm' | 'md' | 'lg' | 'icon'
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'ghost', size = 'md', loading, className, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-2 font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 disabled:pointer-events-none disabled:opacity-40 select-none rounded-lg',
        {
          'bg-accent hover:bg-accent-hover text-white shadow-sm': variant === 'primary',
          'hover:bg-white/5 text-text-secondary hover:text-text-primary': variant === 'ghost',
          'border border-border-default hover:bg-white/5 text-text-secondary hover:text-text-primary': variant === 'outline',
          'hover:bg-red-500/10 text-red-400 hover:text-red-300': variant === 'danger',
          'h-7 px-2.5 text-xs': size === 'sm',
          'h-9 px-3.5 text-sm': size === 'md',
          'h-11 px-5 text-base': size === 'lg',
          'h-8 w-8 p-0': size === 'icon',
        },
        className
      )}
      {...props}
    >
      {loading ? <span className="h-4 w-4 rounded-full border-2 border-current border-t-transparent animate-spin" /> : children}
    </button>
  )
)
Button.displayName = 'Button'
