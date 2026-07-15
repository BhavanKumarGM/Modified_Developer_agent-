import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Project, FileNode, FileContent, GitSnapshot } from '@/types'

interface ProjectStore {
  projects: Project[]
  activeProject: Project | null
  fileTree: FileNode[]
  openFiles: FileContent[]
  activeFilePath: string | null
  gitHistory: GitSnapshot[]

  setProjects: (projects: Project[]) => void
  addProject: (project: Project) => void
  setActiveProject: (project: Project | null) => void
  updateProject: (id: string, updates: Partial<Project>) => void
  removeProject: (id: string) => void

  setFileTree: (tree: FileNode[]) => void
  toggleFolder: (path: string) => void

  openFile: (file: FileContent) => void
  closeFile: (path: string) => void
  setActiveFile: (path: string) => void
  updateFileContent: (path: string, content: string) => void
  markFileDirty: (path: string, dirty: boolean) => void

  setGitHistory: (history: GitSnapshot[]) => void
  addSnapshot: (snapshot: GitSnapshot) => void
}

export const useProjectStore = create<ProjectStore>()(
  persist(
    (set) => ({
      projects: [],
      activeProject: null,
      fileTree: [],
      openFiles: [],
      activeFilePath: null,
      gitHistory: [],

      setProjects: (projects) => set({ projects }),
      addProject: (project) => set((s) => ({ projects: [project, ...s.projects] })),
      setActiveProject: (project) => set({ activeProject: project, fileTree: [], openFiles: [], activeFilePath: null }),
      updateProject: (id, updates) =>
        set((s) => ({
          projects: s.projects.map((p) => (p.id === id ? { ...p, ...updates } : p)),
          activeProject: s.activeProject?.id === id ? { ...s.activeProject, ...updates } : s.activeProject,
        })),
      removeProject: (id) =>
        set((s) => ({
          projects: s.projects.filter((p) => p.id !== id),
          activeProject: s.activeProject?.id === id ? null : s.activeProject,
        })),

      setFileTree: (fileTree) => set({ fileTree }),
      toggleFolder: (path) =>
        set((s) => ({
          fileTree: toggleNode(s.fileTree, path),
        })),

      openFile: (file) =>
        set((s) => {
          const exists = s.openFiles.find((f) => f.path === file.path)
          return {
            openFiles: exists ? s.openFiles : [...s.openFiles, file],
            activeFilePath: file.path,
          }
        }),
      closeFile: (path) =>
        set((s) => {
          const filtered = s.openFiles.filter((f) => f.path !== path)
          const nextActive =
            s.activeFilePath === path ? (filtered.at(-1)?.path ?? null) : s.activeFilePath
          return { openFiles: filtered, activeFilePath: nextActive }
        }),
      setActiveFile: (path) => set({ activeFilePath: path }),
      updateFileContent: (path, content) =>
        set((s) => ({
          openFiles: s.openFiles.map((f) => (f.path === path ? { ...f, content } : f)),
        })),
      markFileDirty: (path, dirty) =>
        set((s) => ({
          openFiles: s.openFiles.map((f) => (f.path === path ? { ...f, isDirty: dirty } : f)),
        })),

      setGitHistory: (gitHistory) => set({ gitHistory }),
      addSnapshot: (snapshot) =>
        set((s) => ({ gitHistory: [snapshot, ...s.gitHistory] })),
    }),
    { name: 'webforge-projects', partialize: (s) => ({ projects: s.projects }) }
  )
)

function toggleNode(nodes: FileNode[], path: string): FileNode[] {
  return nodes.map((n) => {
    if (n.path === path) return { ...n, isExpanded: !n.isExpanded }
    if (n.children) return { ...n, children: toggleNode(n.children, path) }
    return n
  })
}
