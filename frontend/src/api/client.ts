import axios, { AxiosInstance, AxiosError } from 'axios'
import toast from 'react-hot-toast'
import { useAuthStore } from '@/stores/authStore'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor — attach token
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor — handle 401 and errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ error?: string; detail?: unknown }>) => {
    if (error.response?.status === 401) {
      const refreshToken = useAuthStore.getState().refreshToken
      if (refreshToken) {
        try {
          const res = await axios.post(`${BASE_URL}/api/v1/auth/refresh`, { refresh_token: refreshToken })
          const { access_token, refresh_token } = res.data
          useAuthStore.getState().setTokens(access_token, refresh_token)
          if (error.config) {
            error.config.headers.Authorization = `Bearer ${access_token}`
            return apiClient.request(error.config)
          }
        } catch {
          useAuthStore.getState().logout()
          window.location.href = '/login'
          return Promise.reject(error)
        }
      } else {
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
    }

    const message = error.response?.data?.error || error.message || 'An unexpected error occurred'
    if (error.response?.status !== 401) {
      toast.error(message, { duration: 4000 })
    }
    return Promise.reject(error)
  }
)

// ── API functions ──────────────────────────────────────

// Auth
export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post('/api/v1/auth/login', { email, password }).then(r => r.data),
  register: (data: { email: string; password: string; full_name: string }) =>
    apiClient.post('/api/v1/auth/register', data).then(r => r.data),
  me: () => apiClient.get('/api/v1/auth/me').then(r => r.data),
}

// Dashboard
export const dashboardApi = {
  getMetrics: () => apiClient.get('/api/v1/dashboard/metrics').then(r => r.data),
}

// Cases
export const casesApi = {
  list: (page = 1, pageSize = 20, status?: string) =>
    apiClient.get('/api/v1/cases', { params: { page, page_size: pageSize, status } }).then(r => r.data),
  get: (id: string) => apiClient.get(`/api/v1/cases/${id}`).then(r => r.data),
  create: (data: { title: string; description?: string; priority?: string; tags?: string[] }) =>
    apiClient.post('/api/v1/cases', data).then(r => r.data),
  update: (id: string, data: Record<string, unknown>) =>
    apiClient.put(`/api/v1/cases/${id}`, data).then(r => r.data),
  delete: (id: string) => apiClient.delete(`/api/v1/cases/${id}`),
}

// Evidence
export const evidenceApi = {
  upload: (caseId: string, files: File[]) => {
    const form = new FormData()
    files.forEach(f => form.append('files', f))
    return apiClient.post(`/api/v1/cases/${caseId}/evidence/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },
  list: (caseId: string) => apiClient.get(`/api/v1/cases/${caseId}/evidence`).then(r => r.data),
  status: (evidenceId: string) => apiClient.get(`/api/v1/evidence/${evidenceId}/status`).then(r => r.data),
  entities: (caseId: string) => apiClient.get(`/api/v1/cases/${caseId}/entities`).then(r => r.data),
  timeline: (caseId: string) => apiClient.get(`/api/v1/cases/${caseId}/timeline`).then(r => r.data),
  graph: (caseId: string) => apiClient.get(`/api/v1/cases/${caseId}/graph`).then(r => r.data),
  threats: (caseId: string) => apiClient.get(`/api/v1/cases/${caseId}/threats`).then(r => r.data),
  reprocess: (evidenceId: string) => apiClient.post(`/api/v1/evidence/${evidenceId}/reprocess`).then(r => r.data),
  getImpact: (evidenceId: string) => apiClient.get(`/api/v1/evidence/${evidenceId}/impact`).then(r => r.data),
  delete: (evidenceId: string) => apiClient.delete(`/api/v1/evidence/${evidenceId}`).then(r => r.data),
}

// Copilot
export const copilotApi = {
  query: (caseId: string, query: string) =>
    apiClient.post(`/api/v1/cases/${caseId}/copilot/query`, { query }).then(r => r.data),
}

// Reports
export const reportsApi = {
  generate: (caseId: string) =>
    apiClient.post(`/api/v1/cases/${caseId}/report/generate`, {}, { responseType: 'blob' }).then(r => r.data),
}
