import { motion } from 'framer-motion'

export function StreamingCursor() {
  return (
    <motion.span
      animate={{ opacity: [1, 1, 0, 0] }}
      transition={{ duration: 0.8, repeat: Infinity, times: [0, 0.5, 0.5, 1], ease: 'linear' }}
      className="inline-block h-4 w-0.5 bg-accent ml-0.5 align-middle"
    />
  )
}
