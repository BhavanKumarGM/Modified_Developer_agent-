import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { useChatStore } from '@/stores/chatStore'
import type { AgentStatus } from '@/types'

const statusColor: Record<AgentStatus, string> = {
  idle: 'bg-text-muted',
  thinking: 'bg-amber-400',
  working: 'bg-accent',
  done: 'bg-emerald-400',
  error: 'bg-red-400',
}

const statusLabel: Record<AgentStatus, string> = {
  idle: 'Idle',
  thinking: 'Thinking',
  working: 'Working',
  done: 'Done',
  error: 'Error',
}

export function AgentStatusPanel() {
  const agents = useChatStore((s) => s.agents)
  const activeAgents = agents.filter((a) => a.status !== 'idle')
  const allIdle = activeAgents.length === 0

  return (
    <div className="p-3 space-y-1">
      {allIdle ? (
        <p className="text-xs text-text-muted text-center py-4">All agents idle</p>
      ) : null}
      {agents.map((agent) => (
        <div
          key={agent.name}
          className={clsx(
            'flex items-center gap-2.5 px-2 py-1.5 rounded-lg transition-colors',
            agent.status !== 'idle' ? 'bg-white/4' : 'opacity-50'
          )}
        >
          <span className="relative flex h-2 w-2 flex-shrink-0">
            <span
              className={clsx(
                'h-2 w-2 rounded-full',
                statusColor[agent.status],
                agent.status === 'working' || agent.status === 'thinking'
                  ? 'animate-pulse-soft'
                  : ''
              )}
            />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-text-primary truncate">{agent.label}</p>
            {agent.task && (
              <p className="text-[10px] text-text-muted truncate">{agent.task}</p>
            )}
          </div>
          <span
            className={clsx(
              'text-[10px] font-medium',
              agent.status === 'idle' ? 'text-text-muted' : 'text-text-secondary'
            )}
          >
            {statusLabel[agent.status]}
          </span>
        </div>
      ))}
    </div>
  )
}
