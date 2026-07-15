import { Zap, Upload, Edit3, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'

const suggestions = [
  {
    icon: Zap,
    title: 'Build a Website',
    prompt: 'Build a SaaS landing page for an AI Healthcare startup with dark theme and pricing section',
    color: 'text-accent',
    bg: 'bg-accent/10',
  },
  {
    icon: Sparkles,
    title: 'Create Component',
    prompt: 'Create a responsive navigation bar with mobile hamburger menu using Tailwind CSS',
    color: 'text-purple-400',
    bg: 'bg-purple-400/10',
  },
  {
    icon: Edit3,
    title: 'Edit Code',
    prompt: 'Add authentication to the existing project with login, signup, and protected routes',
    color: 'text-emerald-400',
    bg: 'bg-emerald-400/10',
  },
  {
    icon: Upload,
    title: 'Upload & Analyze',
    prompt: 'Upload a ZIP file to analyze your existing project and get improvement suggestions',
    color: 'text-amber-400',
    bg: 'bg-amber-400/10',
  },
]

interface WelcomeScreenProps {
  onSuggestion: (prompt: string) => void
}

export function WelcomeScreen({ onSuggestion }: WelcomeScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="text-center mb-10"
      >
        <div className="inline-flex h-16 w-16 rounded-2xl bg-gradient-to-br from-accent to-purple-600 items-center justify-center mb-4 shadow-lg shadow-accent/20">
          <span className="text-white text-2xl font-bold">W</span>
        </div>
        <h1 className="text-2xl font-semibold text-text-primary mb-2">WebForge AI</h1>
        <p className="text-text-secondary text-sm max-w-sm">
          Your local AI software engineering platform. Build, edit, and optimize websites with natural language.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="grid grid-cols-2 gap-3 w-full max-w-lg"
      >
        {suggestions.map(({ icon: Icon, title, prompt, color, bg }) => (
          <button
            key={title}
            onClick={() => onSuggestion(prompt)}
            className="group flex flex-col gap-2.5 rounded-2xl border border-border-subtle bg-surface-2 p-4 text-left hover:bg-surface-3 hover:border-border-default transition-all duration-200"
          >
            <div className={`inline-flex h-8 w-8 rounded-xl ${bg} items-center justify-center`}>
              <Icon className={`h-4 w-4 ${color}`} />
            </div>
            <div>
              <p className="text-sm font-medium text-text-primary mb-0.5">{title}</p>
              <p className="text-xs text-text-muted line-clamp-2 leading-relaxed">{prompt}</p>
            </div>
          </button>
        ))}
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="mt-8 text-xs text-text-muted"
      >
        Powered by Ollama · Qwen 2.5 · 100% Local
      </motion.p>
    </div>
  )
}
