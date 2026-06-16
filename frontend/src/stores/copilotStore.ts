import { create } from 'zustand'

interface CopilotState {
  queries: Record<string, string>
  histories: Record<string, Array<{ q: string; r: any }>>
  loadingStates: Record<string, boolean>
  setQuery: (caseId: string, query: string) => void
  setHistory: (caseId: string, history: Array<{ q: string; r: any }>) => void
  addHistory: (caseId: string, item: { q: string; r: any }) => void
  setLoading: (caseId: string, loading: boolean) => void
}

export const useCopilotStore = create<CopilotState>((set) => ({
  queries: {},
  histories: {},
  loadingStates: {},
  setQuery: (caseId, query) => set((state) => ({ queries: { ...state.queries, [caseId]: query } })),
  setHistory: (caseId, history) => set((state) => ({ histories: { ...state.histories, [caseId]: history } })),
  addHistory: (caseId, item) => set((state) => ({ 
    histories: { ...state.histories, [caseId]: [...(state.histories[caseId] || []), item] } 
  })),
  setLoading: (caseId, loading) => set((state) => ({ loadingStates: { ...state.loadingStates, [caseId]: loading } })),
}))
