import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { DeviceMode } from '@/types'

type SidebarPanel = 'projects' | 'files' | 'agents' | 'git' | 'memory' | 'settings'

interface UIStore {
  sidebarPanel: SidebarPanel
  sidebarWidth: number
  previewWidth: number
  isSidebarCollapsed: boolean
  isPreviewVisible: boolean
  deviceMode: DeviceMode
  isEditorVisible: boolean
  editorHeight: number

  setSidebarPanel: (panel: SidebarPanel) => void
  setSidebarWidth: (w: number) => void
  setPreviewWidth: (w: number) => void
  toggleSidebar: () => void
  setPreviewVisible: (v: boolean) => void
  setDeviceMode: (mode: DeviceMode) => void
  setEditorVisible: (v: boolean) => void
  setEditorHeight: (h: number) => void
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      sidebarPanel: 'projects',
      sidebarWidth: 260,
      previewWidth: 420,
      isSidebarCollapsed: false,
      isPreviewVisible: true,
      deviceMode: 'desktop',
      isEditorVisible: false,
      editorHeight: 300,

      setSidebarPanel: (sidebarPanel) => set({ sidebarPanel }),
      setSidebarWidth: (sidebarWidth) => set({ sidebarWidth }),
      setPreviewWidth: (previewWidth) => set({ previewWidth }),
      toggleSidebar: () => set((s) => ({ isSidebarCollapsed: !s.isSidebarCollapsed })),
      setPreviewVisible: (isPreviewVisible) => set({ isPreviewVisible }),
      setDeviceMode: (deviceMode) => set({ deviceMode }),
      setEditorVisible: (isEditorVisible) => set({ isEditorVisible }),
      setEditorHeight: (editorHeight) => set({ editorHeight }),
    }),
    { name: 'webforge-ui' }
  )
)
