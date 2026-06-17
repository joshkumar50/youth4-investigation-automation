import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Plus, Search, Filter, FolderOpen, Clock, ChevronRight,
  FileText, Users, Network, X, AlertTriangle, Loader2,
  Trash2, Calendar
} from 'lucide-react'
import toast from 'react-hot-toast'
import { casesApi } from '@/api/client'
import type { Case, CasePriority, CaseStatus } from '@/types'
import { formatDistanceToNow } from 'date-fns'
import { useAuthStore } from '@/stores/authStore'

const PRIORITY_CONFIG: Record<CasePriority, { class: string; glow: string }> = {
  critical: { class: 'badge-critical', glow: 'hover:shadow-glow-red' },
  high: { class: 'badge-high', glow: '' },
  medium: { class: 'badge-medium', glow: '' },
  low: { class: 'badge-low', glow: '' },
}

const STATUS_CONFIG: Record<CaseStatus, string> = {
  active: 'badge-low',
  closed: 'badge-neutral',
  archived: 'badge-neutral',
  pending_review: 'badge-medium',
}

function CreateCaseModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const [form, setForm] = useState({
    title: '',
    description: '',
    priority: 'medium' as CasePriority,
    tags: '',
  })

  const mutation = useMutation({
    mutationFn: () => casesApi.create({
      title: form.title,
      description: form.description || undefined,
      priority: form.priority,
      tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : undefined,
    }),
    onSuccess: (data) => {
      toast.success(`Case "${data.title}" created!`)
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-metrics'] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-lg p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-slate-900">New Investigation Case</h2>
            <p className="text-sm text-slate-500 mt-0.5">Create a new case to begin evidence processing</p>
          </div>
          <button type="button" onClick={onClose} className="btn-ghost p-2">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); mutation.mutate() }} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Case Title *</label>
            <input
              type="text"
              className="input"
              placeholder="Operation Nightfall"
              value={form.title}
              onChange={e => setForm({ ...form, title: e.target.value })}
              required
              minLength={3}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Description</label>
            <textarea
              className="input h-24 resize-none"
              placeholder="Brief description of the investigation..."
              value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Priority</label>
            <div className="grid grid-cols-4 gap-2">
              {(['critical', 'high', 'medium', 'low'] as CasePriority[]).map(p => {
                const isSelected = form.priority === p;
                const ringColor = p === 'critical' ? 'ring-red-400' : p === 'high' ? 'ring-orange-400' : p === 'medium' ? 'ring-amber-400' : 'ring-emerald-400';
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setForm({ ...form, priority: p })}
                    className={`py-2 px-3 rounded-lg text-xs font-medium capitalize transition-all ${
                      isSelected 
                        ? `${PRIORITY_CONFIG[p].class} ring-2 ring-offset-1 ${ringColor}`
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {p}
                  </button>
                )
              })}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Tags</label>
            <input
              type="text"
              className="input"
              placeholder="cybercrime, financial, terrorism (comma separated)"
              value={form.tags}
              onChange={e => setForm({ ...form, tags: e.target.value })}
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={mutation.isPending || !form.title} className="btn-primary flex-1 flex items-center justify-center gap-2">
              {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              Create Case
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  )
}

export default function CaseListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [showCreate, setShowCreate] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<CaseStatus | ''>('')
  
  const [caseToDelete, setCaseToDelete] = useState<Case | null>(null)

  const deleteCaseMutation = useMutation({
    mutationFn: (id: string) => casesApi.delete(id),
    onSuccess: () => {
      toast.success('Case deleted successfully')
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-metrics'] })
      setCaseToDelete(null)
    },
    onError: () => toast.error('Failed to delete case')
  })

  React.useEffect(() => {
    if (searchParams.get('create') === 'true') {
      setShowCreate(true)
      // Remove the query param so it doesn't re-trigger if they refresh
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, setSearchParams])

  const { data, isLoading } = useQuery({
    queryKey: ['cases', statusFilter],
    queryFn: () => casesApi.list(1, 50, statusFilter || undefined),
    refetchInterval: 20000,
  })

  const cases: Case[] = data?.items || []
  const filtered = cases.filter(c =>
    c.title.toLowerCase().includes(search.toLowerCase()) ||
    c.case_number.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="page animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Investigation Cases</h1>
          <p className="text-slate-600 text-sm mt-0.5">{data?.total ?? 0} total cases</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" /> New Case
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            className="input pl-10"
            placeholder="Search cases..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <select
          className="input w-48"
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value as CaseStatus | '')}
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="pending_review">Pending Review</option>
          <option value="closed">Closed</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {/* Cases Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton h-44 rounded-xl" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card p-16 text-center">
          <FolderOpen className="w-14 h-14 mx-auto mb-4 text-slate-600" />
          <p className="text-slate-700 font-semibold text-lg">
            {search ? 'No matching cases' : 'No cases yet'}
          </p>
          <p className="text-slate-500 mt-1 mb-6">
            {search ? 'Try a different search term' : 'Create your first investigation case'}
          </p>
          {!search && (
            <button onClick={() => setShowCreate(true)} className="btn-primary mx-auto flex items-center gap-2 w-fit">
              <Plus className="w-4 h-4" /> Create First Case
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((c, i) => (
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => navigate(`/cases/${c.id}`)}
              className="card-hover p-5 cursor-pointer group"
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-2 mb-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`badge ${PRIORITY_CONFIG[c.priority].class}`}>
                    {c.priority.toUpperCase()}
                  </span>
                  <span className={`badge ${STATUS_CONFIG[c.status]}`}>
                    {c.status.replace('_', ' ')}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-600 font-mono">{c.case_number}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setCaseToDelete(c);
                    }}
                    className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title="Delete Case"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <h3 className="font-semibold text-slate-900 group-hover:text-primary-600 transition-colors line-clamp-2 mb-1">
                {c.title}
              </h3>
              {c.description && (
                <p className="text-sm text-slate-500 line-clamp-2 mb-3">{c.description}</p>
              )}

              {/* Tags */}
              {c.tags && c.tags.length > 0 && (
                <div className="flex gap-1 flex-wrap mb-3">
                  {c.tags.slice(0, 3).map(tag => (
                    <span key={tag} className="badge badge-neutral text-xs">{tag}</span>
                  ))}
                  {c.tags.length > 3 && <span className="text-xs text-slate-600">+{c.tags.length - 3}</span>}
                </div>
              )}

              {/* Metrics */}
              {c.metrics && (
                <div className="grid grid-cols-3 gap-2 pt-3 border-t border-slate-200/50">
                  {[
                    { icon: FileText, value: c.metrics.total_evidence, label: 'Files' },
                    { icon: Users, value: c.metrics.total_entities, label: 'Entities' },
                    { icon: Network, value: c.metrics.total_relationships, label: 'Links' },
                  ].map(({ icon: Icon, value, label }) => (
                    <div key={label} className="flex items-center gap-1.5 text-xs text-slate-500">
                      <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="font-semibold text-slate-700">{value}</span>
                      <span>{label}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between mt-3">
                <span className="text-xs text-slate-600 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatDistanceToNow(new Date(c.updated_at))} ago
                </span>
                <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-primary-600 group-hover:translate-x-0.5 transition-all" />
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <AnimatePresence>
        {showCreate && <CreateCaseModal onClose={() => setShowCreate(false)} />}
      </AnimatePresence>

      {/* Case Deletion Modal */}
      <AnimatePresence>
        {caseToDelete && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden"
            >
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-500" />
                    Delete Case
                  </h3>
                  <button onClick={() => setCaseToDelete(null)} className="text-slate-400 hover:text-slate-600">
                    <X className="w-5 h-5" />
                  </button>
                </div>
                
                <p className="text-slate-600 mb-4">
                  Are you sure you want to delete <strong>{caseToDelete.title}</strong>?
                </p>

                <div className="bg-red-50 border border-red-100 rounded-xl p-4 mb-6">
                  <p className="text-sm font-medium text-red-800 mb-2">This action is irreversible and will destroy:</p>
                  <ul className="space-y-1 text-sm text-red-700">
                    <li className="flex items-center gap-2">
                      <FileText className="w-4 h-4" /> <strong>{caseToDelete.metrics?.total_evidence || 0}</strong> evidence files
                    </li>
                    <li className="flex items-center gap-2">
                      <Users className="w-4 h-4" /> <strong>{caseToDelete.metrics?.total_entities || 0}</strong> extracted entities
                    </li>
                    <li className="flex items-center gap-2">
                      <Network className="w-4 h-4" /> <strong>{caseToDelete.metrics?.total_relationships || 0}</strong> relationships
                    </li>
                    <li className="flex items-center gap-2">
                      <Calendar className="w-4 h-4" /> <strong>{caseToDelete.metrics?.total_timeline_events || 0}</strong> timeline events
                    </li>
                  </ul>
                  <p className="text-xs text-red-600 mt-3 italic text-center border-t border-red-200/50 pt-2">
                    Cross-case links to these entities will also be broken.
                  </p>
                </div>

                <div className="flex justify-end gap-3 mt-6">
                  <button
                    onClick={() => setCaseToDelete(null)}
                    className="btn-secondary"
                    disabled={deleteCaseMutation.isPending}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => deleteCaseMutation.mutate(caseToDelete.id)}
                    className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-xl font-medium transition-colors flex items-center gap-2"
                    disabled={deleteCaseMutation.isPending}
                  >
                    {deleteCaseMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                    Yes, Delete Case
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
