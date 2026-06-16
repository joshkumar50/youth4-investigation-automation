import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Shield, Eye, EyeOff, Lock, Mail, User, ChevronRight, Zap } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '@/api/client'
import { useAuthStore } from '@/stores/authStore'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setTokens, setUser } = useAuthStore()
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ email: '', password: '', full_name: '' })

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const tokens = await authApi.login(form.email, form.password)
      setTokens(tokens.access_token, tokens.refresh_token)
      const user = await authApi.me()
      setUser(user)
      toast.success(`Welcome back, ${user.full_name}!`)
      navigate('/dashboard')
    } catch {
      // Error handled by axios interceptor
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await authApi.register(form)
      toast.success('Account created! Please sign in.')
      setTab('login')
    } catch {
      // handled
    } finally {
      setLoading(false)
    }
  }

  const handleDemoLogin = async () => {
    setForm({ email: 'demo@iip.gov', password: 'Demo1234!', full_name: '' })
    setLoading(true)
    try {
      const tokens = await authApi.login('demo@iip.gov', 'Demo1234!')
      setTokens(tokens.access_token, tokens.refresh_token)
      const user = await authApi.me()
      setUser(user)
      toast.success('Demo mode activated!')
      navigate('/dashboard')
    } catch {
      toast.error('Demo account not seeded yet. Run: python scripts/seed_demo_data.py')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-50 grid-pattern flex">
      {/* Left Panel — Branding */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 p-12 bg-white border-r border-slate-200 relative overflow-hidden">
        {/* Background glow */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary-600/5 rounded-full blur-3xl" />
          <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-violet-600/5 rounded-full blur-3xl" />
        </div>

        {/* Logo */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 relative z-10"
        >
          <div className="p-2.5 rounded-xl bg-primary-50 border border-primary-100">
            <Shield className="w-7 h-7 text-primary-600" />
          </div>
          <div>
            <div className="font-bold text-slate-900 text-lg leading-tight">Investigation</div>
            <div className="font-bold text-primary-600 text-lg leading-tight">Intelligence Platform</div>
          </div>
        </motion.div>

        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="relative z-10"
        >
          <div className="badge badge-info mb-6 w-fit">
            <Zap className="w-3 h-3" /> AI-Powered Investigation
          </div>
          <h1 className="text-4xl font-bold text-slate-900 leading-tight mb-4">
            Transform Evidence into
            <span className="text-primary-600 block">Investigation Intelligence</span>
          </h1>
          <p className="text-slate-600 text-lg leading-relaxed mb-8">
            Upload raw digital evidence. Our AI pipeline automatically extracts entities, 
            reconstructs timelines, maps relationships, and generates actionable insights.
          </p>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { value: '11', label: 'AI Modules' },
              { value: '75%', label: 'Time Saved' },
              { value: '99%', label: 'Accuracy' },
            ].map((stat) => (
              <div key={stat.label} className="card p-4 text-center border-slate-200 bg-slate-50">
                <div className="text-2xl font-bold text-primary-600">{stat.value}</div>
                <div className="text-xs text-slate-500 mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Features list */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="relative z-10 space-y-2"
        >
          {[
            'Automated OCR & text extraction',
            'Named entity recognition (NER)',
            'Timeline reconstruction',
            'Relationship intelligence graph',
            'AI-powered investigation copilot',
          ].map((f) => (
            <div key={f} className="flex items-center gap-2 text-sm text-slate-600">
              <ChevronRight className="w-4 h-4 text-primary-500 flex-shrink-0" />
              {f}
            </div>
          ))}
        </motion.div>
      </div>

      {/* Right Panel — Auth Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="w-full max-w-md"
        >
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="p-2 rounded-xl bg-primary-50 border border-primary-100">
              <Shield className="w-6 h-6 text-primary-600" />
            </div>
            <div className="font-bold text-slate-900 text-lg">Investigation Intelligence Platform</div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 p-1 bg-white rounded-xl mb-8 border border-slate-200/50">
            {(['login', 'register'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 py-2.5 text-sm font-semibold rounded-lg transition-all duration-200 ${
                  tab === t
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                {t === 'login' ? 'Sign In' : 'Create Account'}
              </button>
            ))}
          </div>

          <form onSubmit={tab === 'login' ? handleLogin : handleRegister} className="space-y-4">
            {tab === 'register' && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Full Name</label>
                <div className="relative">
                  <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type="text"
                    className="input pl-10"
                    placeholder="Detective Sarah Connor"
                    value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    required
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Email Address</label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type="email"
                  className="input pl-10"
                  placeholder="investigator@agency.gov"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="input pl-10 pr-10"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 py-3 mt-2"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  {tab === 'login' ? 'Sign In' : 'Create Account'}
                  <ChevronRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200/50" />
            </div>
            <div className="relative flex justify-center text-xs text-slate-500 uppercase tracking-widest">
              <span className="px-3 bg-surface-50">or</span>
            </div>
          </div>

          <button
            onClick={handleDemoLogin}
            disabled={loading}
            className="btn-secondary w-full flex items-center justify-center gap-2"
          >
            <Zap className="w-4 h-4 text-amber-400" />
            Quick Demo Access
          </button>

          <p className="mt-6 text-center text-xs text-slate-500">
            Restricted access. Authorized law enforcement personnel only.
          </p>
        </motion.div>
      </div>
    </div>
  )
}
