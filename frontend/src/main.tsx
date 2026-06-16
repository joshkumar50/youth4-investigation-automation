import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'

import './index.css'
import { useAuthStore } from '@/stores/authStore'
import AppLayout from '@/components/layout/AppLayout'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import CaseListPage from '@/pages/CaseListPage'
import CasePage from '@/pages/CasePage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 10000,
      refetchOnWindowFocus: false,
    },
  },
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <AppLayout>{children}</AppLayout>
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/cases" element={<ProtectedRoute><CaseListPage /></ProtectedRoute>} />
          <Route path="/cases/:caseId" element={<ProtectedRoute><CasePage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#ffffff',
            color: '#1e293b',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            fontSize: '14px',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
          },
          success: { iconTheme: { primary: '#10b981', secondary: '#ffffff' } },
          error: { iconTheme: { primary: '#ef4444', secondary: '#ffffff' } },
          duration: 3500,
        }}
      />
    </QueryClientProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
