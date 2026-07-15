import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Copy, Check, Bot, User, Cpu } from 'lucide-react'
import { clsx } from 'clsx'
import { motion } from 'framer-motion'
import { StreamingCursor } from './StreamingCursor'
import { Badge } from '@/components/ui/Badge'
import type { Message } from '@/types'

interface CopyButtonProps {
  code: string
}

function CopyButton({ code }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button
      onClick={copy}
      className="absolute right-2 top-2 p-1.5 rounded-md bg-white/5 hover:bg-white/10 text-text-muted hover:text-text-primary transition-colors"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

const agentColors: Record<string, string> = {
  planner: 'text-amber-400', codegen: 'text-blue-400', editing: 'text-purple-400',
  review: 'text-emerald-400', validation: 'text-cyan-400', debug: 'text-red-400',
  repository: 'text-orange-400', search: 'text-yellow-400', memory: 'text-pink-400',
  design: 'text-indigo-400', git: 'text-teal-400', preview: 'text-green-400',
}

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isAgent = message.role === 'agent'
  const isStreaming = message.isStreaming

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={clsx('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}
    >
      {/* Avatar */}
      <div className={clsx(
        'flex-shrink-0 h-7 w-7 rounded-full flex items-center justify-center text-xs font-medium mt-0.5',
        isUser
          ? 'bg-accent text-white'
          : isAgent
          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/20'
          : 'bg-surface-4 border border-border-default text-accent'
      )}>
        {isUser ? <User className="h-3.5 w-3.5" /> : isAgent ? <Cpu className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
      </div>

      {/* Content */}
      <div className={clsx('flex flex-col gap-1 max-w-[85%]', isUser && 'items-end')}>
        {/* Agent label */}
        {isAgent && message.agentName && (
          <span className={clsx(
            'text-[10px] font-semibold uppercase tracking-wide px-1',
            agentColors[message.agentName] ?? 'text-text-muted'
          )}>
            {message.agentName} agent
          </span>
        )}

        {/* Bubble */}
        <div className={clsx(
          'rounded-2xl px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'bg-accent/90 text-white rounded-tr-sm'
            : 'bg-surface-3 border border-border-subtle text-text-primary rounded-tl-sm'
        )}>
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none prose-pre:p-0 prose-pre:bg-transparent prose-code:text-accent prose-code:bg-accent/10 prose-code:rounded prose-code:px-1 prose-code:py-0.5 prose-code:text-xs prose-code:font-mono">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className ?? '')
                    const code = String(children).replace(/\n$/, '')
                    const isInline = !match

                    if (isInline) {
                      return <code className={className} {...props}>{children}</code>
                    }

                    return (
                      <div className="relative my-3 rounded-xl overflow-hidden border border-border-subtle">
                        <div className="flex items-center justify-between px-3 py-1.5 bg-surface-4 border-b border-border-subtle">
                          <span className="text-[10px] text-text-muted font-mono">{match[1]}</span>
                          <CopyButton code={code} />
                        </div>
                        <SyntaxHighlighter
                          style={vscDarkPlus}
                          language={match[1]}
                          PreTag="div"
                          customStyle={{
                            margin: 0,
                            borderRadius: 0,
                            background: '#0f0f1a',
                            fontSize: '12px',
                            padding: '12px 16px',
                          }}
                        >
                          {code}
                        </SyntaxHighlighter>
                      </div>
                    )
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
              {isStreaming && <StreamingCursor />}
            </div>
          )}
        </div>

        {/* File refs */}
        {message.fileRefs && message.fileRefs.length > 0 && (
          <div className="flex flex-wrap gap-1 px-1">
            {message.fileRefs.map((ref) => (
              <Badge key={ref.path} variant="muted">
                {ref.path}
              </Badge>
            ))}
          </div>
        )}

        {/* Timestamp */}
        <span className="text-[10px] text-text-muted px-1">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </motion.div>
  )
}
