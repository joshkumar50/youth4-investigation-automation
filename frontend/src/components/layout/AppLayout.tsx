import React from 'react'
import { NavLink, Link, useNavigate } from 'react-router-dom'
import {
  Shield, LayoutDashboard, FolderOpen, FileSearch,
  LogOut, User, Settings, ChevronDown,
} from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import toast from 'react-hot-toast'

const NAV_ITEMS = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/cases', icon: FolderOpen, label: 'Cases' },
]

function Sidebar() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    toast.success('Logged out successfully')
    navigate('/login')
  }

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="p-5 border-b border-slate-200/50">
        <Link to="/dashboard" className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-primary-50 border border-primary-100">
            <Shield className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-900 leading-tight">Investigation</div>
            <div className="text-xs text-primary-600 font-bold leading-tight">Intelligence Platform</div>
            <div className="text-[10px] text-slate-500 font-mono mt-0.5">Mission Y4 Edition</div>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-1">
        <div className="section-label px-3 mt-2">Navigation</div>
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* System Status */}
      <div className="p-3 mx-3 mb-3 rounded-lg bg-emerald-50 border border-emerald-100">
        <div className="flex items-center gap-2 mb-1.5">
          <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
          <span className="text-xs font-semibold text-emerald-600">All Systems Operational</span>
        </div>
        <div className="space-y-0.5">
          {['API', 'Workers', 'AI Engine', 'Storage'].map(s => (
            <div key={s} className="flex items-center justify-between text-xs text-slate-500">
              <span>{s}</span>
              <span className="text-emerald-600">●</span>
            </div>
          ))}
        </div>
      </div>

      {/* User */}
      <div className="p-3 border-t border-slate-200/50">
        <div className="flex items-center gap-2.5 p-2.5 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer">
          <div className="w-8 h-8 rounded-lg bg-primary-50 border border-primary-100 flex items-center justify-center flex-shrink-0">
            <User className="w-4 h-4 text-primary-600" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-slate-800 truncate">{user?.full_name}</div>
            <div className="text-xs text-slate-500 capitalize">{user?.role}</div>
          </div>
          <button onClick={handleLogout} className="p-1.5 rounded-lg hover:bg-red-50 text-slate-500 hover:text-red-600 transition-colors" title="Logout">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  )
}

function Topbar() {
  const navigate = useNavigate()

  return (
    <header className="topbar left-64">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <span className="font-mono text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded border border-slate-200/50">
          IIP v1.0.0
        </span>
      </div>
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/cases?create=true')}
          className="btn-primary text-sm flex items-center gap-1.5 py-2"
        >
          <FolderOpen className="w-4 h-4" /> New Case
        </button>
      </div>
    </header>
  )
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-surface-50 grid-pattern bg-fixed">
      <Sidebar />
      <Topbar />
      <main>{children}</main>
    </div>
  )
}
