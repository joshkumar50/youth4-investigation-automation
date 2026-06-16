import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import {
  Shield, FolderOpen, FileSearch, Users, Clock, TrendingUp,
  AlertTriangle, CheckCircle, Activity, ArrowRight, Zap, Database,
} from 'lucide-react'
import { dashboardApi } from '@/api/client'
import type { DashboardMetrics } from '@/types'
import { useAuthStore } from '@/stores/authStore'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'

const PIE_COLORS = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

const MOCK_ACTIVITY = [
  { time: '00:00', cases: 2 }, { time: '04:00', cases: 5 },
  { time: '08:00', cases: 12 }, { time: '12:00', cases: 18 },
  { time: '16:00', cases: 14 }, { time: '20:00', cases: 9 }, { time: '23:59', cases: 6 },
]

function StatCard({ icon: Icon, label, value, sub, color = 'primary', delay = 0 }: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string | number
  sub?: string
  color?: string
  delay?: number
}) {
  const colorMap: Record<string, string> = {
    primary: 'text-primary-600 bg-primary-50 border-primary-100 shadow-sm',
    violet: 'text-violet-400 bg-violet-500/10 border-violet-500/30 shadow-[inset_0_0_12px_rgba(139,92,246,0.2)]',
    emerald: 'text-emerald-600 bg-emerald-50 border-emerald-100 shadow-sm',
    amber: 'text-amber-400 bg-amber-500/10 border-amber-500/30 shadow-[inset_0_0_12px_rgba(245,158,11,0.2)]',
    red: 'text-red-400 bg-red-500/10 border-red-500/30 shadow-[inset_0_0_12px_rgba(239,68,68,0.2)]',
    cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30 shadow-[inset_0_0_12px_rgba(6,182,212,0.2)]',
  }
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="card-hover p-6 flex flex-col relative overflow-hidden group"
    >
      <div className="absolute top-0 right-0 w-32 h-32 bg-slate-100 rounded-full blur-3xl -mr-10 -mt-10 group-hover:bg-slate-200 transition-colors" />
      <div className={`p-3 rounded-xl border w-fit ${colorMap[color] || colorMap.primary}`}>
        <Icon className="w-6 h-6" />
      </div>
      <div className="text-3xl font-bold text-slate-900 mt-4 tracking-tight">{value}</div>
      <div className="text-sm font-medium text-slate-600 mt-1">{label}</div>
      {sub && <div className="text-xs text-slate-500 mt-1 font-mono uppercase tracking-wider">{sub}</div>}
    </motion.div>
  )
}

export default function DashboardPage() {
  const { user } = useAuthStore()
  const { data: metrics, isLoading } = useQuery<DashboardMetrics>({
    queryKey: ['dashboard-metrics'],
    queryFn: dashboardApi.getMetrics,
    refetchInterval: 30000,
  })

  const greeting = () => {
    const h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 18) return 'Good afternoon'
    return 'Good evening'
  }

  const priorityData = metrics
    ? Object.entries(metrics.cases_by_priority).map(([name, value]) => ({ name, value }))
    : []

  return (
    <div className="page animate-fade-in">
      {/* Header */}
      <div className="mb-8">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            <span className="text-xs text-slate-500 font-medium uppercase tracking-widest">System Online</span>
          </div>
          <h1 className="text-3xl font-bold text-slate-900">
            {greeting()}, {user?.full_name?.split(' ')[0] || 'Investigator'} 👋
          </h1>
          <p className="text-slate-600 mt-1">
            Investigation Intelligence Dashboard — Real-time evidence analytics
          </p>
        </motion.div>
      </div>

      {/* Impact Banner */}
      {metrics && metrics.total_processing_time_saved_hours > 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="mb-8 relative overflow-hidden rounded-2xl bg-white/80 backdrop-blur-xl border border-primary-100 
                     shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1),0_0_30px_rgba(59,130,246,0.15)] flex items-center justify-between p-1"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-primary-500/10 via-transparent to-violet-500/10" />
          <div className="relative flex items-center gap-4 px-5 py-4">
            <div className="relative p-3 rounded-xl bg-primary-50 border border-primary-200 shadow-sm">
              <Zap className="w-6 h-6 text-primary-600 animate-pulse-slow" />
            </div>
            <div>
              <div className="text-lg font-bold text-slate-900 tracking-tight">
                AI Pipeline has saved{' '}
                <span className="text-gradient bg-clip-text text-transparent bg-gradient-to-r from-primary-400 to-violet-400">
                  {metrics.total_processing_time_saved_hours.toFixed(0)} hours
                </span>
                {' '}of manual investigation
              </div>
              <div className="text-sm text-slate-600 font-medium">Accelerated processing across {metrics.total_evidence_files} digital evidence files</div>
            </div>
          </div>
          <div className="relative px-5">
            <Link to="/cases" className="btn-primary flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold uppercase tracking-wider">
              Open Cases <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </motion.div>
      )}

      {/* KPI Grid */}
      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton h-32 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
          <StatCard icon={FolderOpen} label="Total Cases" value={metrics?.total_cases ?? 0} color="primary" delay={0} />
          <StatCard icon={Activity} label="Active Cases" value={metrics?.active_cases ?? 0} color="emerald" delay={0.05} />
          <StatCard icon={FileSearch} label="Evidence Files" value={metrics?.total_evidence_files ?? 0} color="violet" delay={0.1} />
          <StatCard icon={Users} label="Entities Detected" value={metrics?.total_entities_detected ?? 0} color="cyan" delay={0.15} />
          <StatCard icon={Clock} label="Hours Saved" value={`${(metrics?.total_processing_time_saved_hours ?? 0).toFixed(0)}h`} color="amber" delay={0.2} />
          <StatCard icon={TrendingUp} label="Avg. Resolution" value={`${metrics?.average_case_resolution_hours ?? 0}h`} sub="per case" color="primary" delay={0.25} />
        </div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Activity Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="card p-5 lg:col-span-2"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-slate-900">Investigation Activity</h3>
              <p className="text-xs text-slate-500">Cases processed over 24h</p>
            </div>
            <div className="badge badge-info"><Activity className="w-3 h-3" /> Live</div>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={MOCK_ACTIVITY}>
              <defs>
                <linearGradient id="actGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 12, boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)' }}
                labelStyle={{ color: '#64748b' }}
              />
              <Area type="monotone" dataKey="cases" stroke="#3b82f6" strokeWidth={2} fill="url(#actGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Priority Pie */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="card p-5"
        >
          <h3 className="font-semibold text-slate-900 mb-1">Cases by Priority</h3>
          <p className="text-xs text-slate-500 mb-4">Distribution</p>
          {priorityData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={140}>
                <PieChart>
                  <Pie data={priorityData} cx="50%" cy="50%" innerRadius={40} outerRadius={65} paddingAngle={3} dataKey="value">
                    {priorityData.map((_, index) => (
                      <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 12, boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)' }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-2">
                {priorityData.map((item, i) => (
                  <div key={item.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-full" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                      <span className="text-slate-600 capitalize">{item.name}</span>
                    </div>
                    <span className="text-slate-700 font-medium">{item.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-32 text-slate-500">
              <Database className="w-8 h-8 mb-2 opacity-40" />
              <span className="text-xs">No case data yet</span>
            </div>
          )}
        </motion.div>
      </div>

      {/* Quick Actions */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="card p-5"
      >
        <h3 className="font-semibold text-slate-900 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { to: '/cases?create=true', icon: FolderOpen, label: 'New Investigation', color: 'primary' },
            { to: '/cases', icon: FileSearch, label: 'Browse Cases', color: 'violet' },
            { to: '/dashboard', icon: AlertTriangle, label: 'View Threats (Soon)', color: 'amber' },
            { to: '/dashboard', icon: CheckCircle, label: 'System Status (Soon)', color: 'emerald' },
          ].map(({ to, icon: Icon, label, color }) => (
            <Link
              key={label}
              to={to}
              className="flex flex-col items-center gap-2 p-4 rounded-xl border border-slate-200/50 
                         hover:border-primary-100 bg-slate-50 hover:bg-surface-100/50 
                         transition-all duration-200 group text-center"
            >
              <div className="p-2.5 rounded-lg bg-primary-50 group-hover:bg-primary-50 transition-colors">
                <Icon className="w-5 h-5 text-primary-600" />
              </div>
              <span className="text-xs font-medium text-slate-700">{label}</span>
            </Link>
          ))}
        </div>
      </motion.div>
    </div>
  )
}
