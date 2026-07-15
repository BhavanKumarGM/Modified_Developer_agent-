import { useEffect, useRef } from 'react'
import Editor, { useMonaco } from '@monaco-editor/react'
import { X, Circle } from 'lucide-react'
import { clsx } from 'clsx'
import { useProjectStore } from '@/stores/projectStore'
import { api } from '@/services/api'

const MONACO_THEME = {
  base: 'vs-dark' as const,
  inherit: true,
  rules: [
    { token: 'comment', foreground: '5a5a70', fontStyle: 'italic' },
    { token: 'keyword', foreground: '818cf8' },
    { token: 'string', foreground: '6ee7b7' },
    { token: 'number', foreground: 'f9a8d4' },
    { token: 'type', foreground: '93c5fd' },
    { token: 'variable', foreground: 'e8e8f0' },
  ],
  colors: {
    'editor.background': '#0f0f1a',
    'editor.foreground': '#e8e8f0',
    'editorLineNumber.foreground': '#3a3a50',
    'editorLineNumber.activeForeground': '#6366f1',
    'editor.selectionBackground': '#6366f125',
    'editor.lineHighlightBackground': '#ffffff06',
    'editorCursor.foreground': '#6366f1',
    'editorIndentGuide.background': '#ffffff08',
    'editorIndentGuide.activeBackground': '#6366f140',
  },
}

const extToLang: Record<string, string> = {
  ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
  css: 'css', html: 'html', json: 'json', py: 'python', md: 'markdown',
  yaml: 'yaml', yml: 'yaml', svg: 'xml', sh: 'shell',
}

function getLanguage(path: string): string {
  const ext = path.split('.').pop() ?? ''
  return extToLang[ext] ?? 'plaintext'
}

export function CodeEditor() {
  const { openFiles, activeFilePath, setActiveFile, closeFile, updateFileContent, markFileDirty, activeProject } =
    useProjectStore()
  const monaco = useMonaco()

  useEffect(() => {
    if (!monaco) return
    monaco.editor.defineTheme('webforge', MONACO_THEME)
    monaco.editor.setTheme('webforge')
  }, [monaco])

  const activeFile = openFiles.find((f) => f.path === activeFilePath)

  const handleSave = async (path: string, content: string) => {
    if (!activeProject) return
    try {
      await api.files.write(activeProject.id, path, content)
      markFileDirty(path, false)
    } catch (e) {
      console.error('Save failed', e)
    }
  }

  if (openFiles.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-sm">
        Open a file from the explorer to start editing
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-surface-1">
      {/* Tabs */}
      <div className="flex items-center gap-0 border-b border-border-subtle overflow-x-auto flex-shrink-0 bg-surface-2">
        {openFiles.map((file) => {
          const name = file.path.split('/').pop() ?? file.path
          const isActive = file.path === activeFilePath
          return (
            <button
              key={file.path}
              onClick={() => setActiveFile(file.path)}
              className={clsx(
                'group flex items-center gap-1.5 px-3 py-2 text-xs border-r border-border-subtle whitespace-nowrap transition-colors flex-shrink-0',
                isActive
                  ? 'bg-surface-1 text-text-primary border-b border-b-accent -mb-px'
                  : 'text-text-muted hover:text-text-secondary hover:bg-white/3'
              )}
            >
              {file.isDirty && <Circle className="h-1.5 w-1.5 fill-accent text-accent" />}
              <span className="font-mono">{name}</span>
              <span
                onClick={(e) => { e.stopPropagation(); closeFile(file.path) }}
                className="ml-0.5 opacity-0 group-hover:opacity-100 rounded hover:bg-white/10 p-0.5 transition-all"
              >
                <X className="h-3 w-3" />
              </span>
            </button>
          )
        })}
      </div>

      {/* Active file path */}
      {activeFilePath && (
        <div className="px-3 py-1 border-b border-border-subtle bg-surface-2">
          <span className="text-[10px] text-text-muted font-mono">{activeFilePath}</span>
        </div>
      )}

      {/* Editor */}
      {activeFile && (
        <div className="flex-1 min-h-0">
          <Editor
            height="100%"
            language={getLanguage(activeFile.path)}
            value={activeFile.content}
            theme="webforge"
            onChange={(val) => {
              if (val !== undefined) {
                updateFileContent(activeFile.path, val)
                markFileDirty(activeFile.path, true)
              }
            }}
            onMount={(editor, monaco) => {
              editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
                handleSave(activeFile.path, editor.getValue())
              })
            }}
            options={{
              fontSize: 13,
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              fontLigatures: true,
              lineHeight: 1.7,
              minimap: { enabled: true },
              scrollBeyondLastLine: false,
              renderLineHighlight: 'line',
              bracketPairColorization: { enabled: true },
              smoothScrolling: true,
              cursorBlinking: 'phase',
              cursorSmoothCaretAnimation: 'on',
              padding: { top: 12, bottom: 12 },
              overviewRulerLanes: 0,
              scrollbar: {
                verticalScrollbarSize: 6,
                horizontalScrollbarSize: 6,
              },
            }}
          />
        </div>
      )}
    </div>
  )
}
