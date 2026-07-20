import { beforeEach, describe, expect, it } from 'vitest'
import { useUIStore } from './uiStore'

const initialState = useUIStore.getState()

beforeEach(() => {
  useUIStore.setState(initialState, true)
  localStorage.clear()
})

describe('uiStore', () => {
  it('defaults to the projects panel, expanded sidebar, desktop device', () => {
    const state = useUIStore.getState()
    expect(state.sidebarPanel).toBe('projects')
    expect(state.isSidebarCollapsed).toBe(false)
    expect(state.deviceMode).toBe('desktop')
  })

  it('setSidebarPanel switches panels', () => {
    useUIStore.getState().setSidebarPanel('files')
    expect(useUIStore.getState().sidebarPanel).toBe('files')
  })

  it('toggleSidebar flips isSidebarCollapsed each call', () => {
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().isSidebarCollapsed).toBe(true)
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().isSidebarCollapsed).toBe(false)
  })

  it('setDeviceMode updates the preview device', () => {
    useUIStore.getState().setDeviceMode('mobile')
    expect(useUIStore.getState().deviceMode).toBe('mobile')
  })

  it('setSidebarWidth and setPreviewWidth update independently', () => {
    useUIStore.getState().setSidebarWidth(320)
    useUIStore.getState().setPreviewWidth(500)

    const state = useUIStore.getState()
    expect(state.sidebarWidth).toBe(320)
    expect(state.previewWidth).toBe(500)
  })

  it('setEditorVisible and setEditorHeight update the editor panel', () => {
    useUIStore.getState().setEditorVisible(true)
    useUIStore.getState().setEditorHeight(450)

    const state = useUIStore.getState()
    expect(state.isEditorVisible).toBe(true)
    expect(state.editorHeight).toBe(450)
  })
})
