import { beforeEach, describe, expect, it } from 'vitest'
import { useProjectStore } from './projectStore'
import type { FileContent, Project } from '@/types'

const initialState = useProjectStore.getState()

beforeEach(() => {
  useProjectStore.setState(initialState, true)
  localStorage.clear()
})

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 'p1',
    name: 'Test Project',
    framework: 'react',
    status: 'ready',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...overrides,
  }
}

describe('projectStore', () => {
  it('addProject prepends to the list', () => {
    useProjectStore.getState().addProject(makeProject({ id: 'p1' }))
    useProjectStore.getState().addProject(makeProject({ id: 'p2' }))

    const ids = useProjectStore.getState().projects.map((p) => p.id)
    expect(ids).toEqual(['p2', 'p1'])
  })

  it('setActiveProject resets fileTree/openFiles/activeFilePath', () => {
    useProjectStore.getState().setFileTree([{ id: 'a', name: 'a.ts', path: 'a.ts', type: 'file' }])
    useProjectStore.getState().openFile({ path: 'a.ts', content: 'x', language: 'typescript' })

    useProjectStore.getState().setActiveProject(makeProject())

    const state = useProjectStore.getState()
    expect(state.activeProject?.id).toBe('p1')
    expect(state.fileTree).toEqual([])
    expect(state.openFiles).toEqual([])
    expect(state.activeFilePath).toBeNull()
  })

  it('updateProject patches both the list entry and activeProject when it matches', () => {
    const project = makeProject()
    useProjectStore.getState().addProject(project)
    useProjectStore.getState().setActiveProject(project)

    useProjectStore.getState().updateProject('p1', { status: 'generating' })

    const state = useProjectStore.getState()
    expect(state.projects[0].status).toBe('generating')
    expect(state.activeProject?.status).toBe('generating')
  })

  it('removeProject clears activeProject only if it was the removed one', () => {
    const project = makeProject()
    useProjectStore.getState().addProject(project)
    useProjectStore.getState().setActiveProject(project)

    useProjectStore.getState().removeProject('p1')

    const state = useProjectStore.getState()
    expect(state.projects).toEqual([])
    expect(state.activeProject).toBeNull()
  })

  it('openFile adds a new file and sets it active, but does not duplicate an already-open file', () => {
    const file: FileContent = { path: 'src/App.tsx', content: 'x', language: 'typescript' }
    useProjectStore.getState().openFile(file)
    useProjectStore.getState().openFile(file)

    const state = useProjectStore.getState()
    expect(state.openFiles).toHaveLength(1)
    expect(state.activeFilePath).toBe('src/App.tsx')
  })

  it('closeFile falls back active file to the last remaining open file', () => {
    useProjectStore.getState().openFile({ path: 'a.tsx', content: '', language: 'typescript' })
    useProjectStore.getState().openFile({ path: 'b.tsx', content: '', language: 'typescript' })

    useProjectStore.getState().closeFile('b.tsx')

    const state = useProjectStore.getState()
    expect(state.openFiles.map((f) => f.path)).toEqual(['a.tsx'])
    expect(state.activeFilePath).toBe('a.tsx')
  })

  it('updateFileContent only updates the matching open file', () => {
    useProjectStore.getState().openFile({ path: 'a.tsx', content: 'old', language: 'typescript' })
    useProjectStore.getState().openFile({ path: 'b.tsx', content: 'old', language: 'typescript' })

    useProjectStore.getState().updateFileContent('a.tsx', 'new')

    const state = useProjectStore.getState()
    expect(state.openFiles.find((f) => f.path === 'a.tsx')?.content).toBe('new')
    expect(state.openFiles.find((f) => f.path === 'b.tsx')?.content).toBe('old')
  })

  it('toggleFolder flips isExpanded for the matching node, including nested children', () => {
    useProjectStore.getState().setFileTree([
      {
        id: 'src',
        name: 'src',
        path: 'src',
        type: 'directory',
        isExpanded: false,
        children: [{ id: 'src/a', name: 'a.ts', path: 'src/a.ts', type: 'file' }],
      },
    ])

    useProjectStore.getState().toggleFolder('src')

    expect(useProjectStore.getState().fileTree[0].isExpanded).toBe(true)
  })
})
