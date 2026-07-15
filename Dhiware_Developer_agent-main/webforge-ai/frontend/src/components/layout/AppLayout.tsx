import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Code2, Eye, MessageSquare } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { ResizablePanel } from './ResizablePanel'
import { ChatWorkspace } from '@/components/chat/ChatWorkspace'
import { PreviewPanel } from '@/components/preview/PreviewPanel'
import { CodeEditor } from '@/components/editor/CodeEditor'
import { Button } from '@/components/ui/Button'
import { useUIStore } from '@/stores/uiStore'
import { useProjectStore } from '@/stores/projectStore'

type ActiveView = 'chat' | 'editor'

export function AppLayout() {
  const { previewWidth, setPreviewWidth, isPreviewVisible, setPreviewVisible, isEditorVisible, setEditorVisible } = useUIStore()
  const openFiles = useProjectStore((s) => s.openFiles)
  const [activeView, setActiveView] = useState<ActiveView>('chat')

  const hasOpenFiles = openFiles.length > 0

  return (
    <div className="flex h-screen overflow-hidden bg-surface-0 text-text-primary">
      {/* Sidebar */}
      <Sidebar />

      {/* Main workspace */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* View toggle bar (when editor is visible) */}
        {hasOpenFiles && (
          <div className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 border-b border-border-subtle bg-surface-1">
            <Button
              variant={activeView === 'chat' ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setActiveView('chat')}
              className="gap-1.5 h-7"
            >
              <MessageSquare className="h-3.5 w-3.5" /> Chat
            </Button>
            <Button
              variant={activeView === 'editor' ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setActiveView('editor')}
              className="gap-1.5 h-7"
            >
              <Code2 className="h-3.5 w-3.5" /> Editor
            </Button>
            <div className="flex-1" />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPreviewVisible(!isPreviewVisible)}
              className={`gap-1.5 h-7 ${isPreviewVisible ? 'text-accent' : ''}`}
            >
              <Eye className="h-3.5 w-3.5" />
              {isPreviewVisible ? 'Hide Preview' : 'Show Preview'}
            </Button>
          </div>
        )}

        <div className="flex flex-1 min-h-0">
          {/* Chat or Editor */}
          <div className="flex-1 min-w-0">
            {activeView === 'chat' || !hasOpenFiles ? (
              <ChatWorkspace />
            ) : (
              <CodeEditor />
            )}
          </div>

          {/* Preview panel */}
          <AnimatePresence initial={false}>
            {isPreviewVisible && (
              <motion.div
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: previewWidth, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                transition={{ type: 'spring', stiffness: 350, damping: 40 }}
                className="relative flex-shrink-0 h-full overflow-hidden"
                style={{ width: previewWidth }}
              >
                {/* Resize handle */}
                <ResizablePanel
                  width={previewWidth}
                  minWidth={280}
                  maxWidth={900}
                  onResize={setPreviewWidth}
                  side="left"
                  className="h-full w-full"
                >
                  <PreviewPanel />
                </ResizablePanel>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
