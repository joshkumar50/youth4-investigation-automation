import React, { useState, useCallback, useRef, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { useDropzone } from 'react-dropzone'
import {
  Upload, FileText, Image, Video, MessageSquare, File,
  ChevronLeft, Play, Clock, Users, Network, AlertTriangle,
  CheckCircle, Loader2, X, Eye, Shield, TrendingUp, Download,
  Bot, Calendar, Copy, Trash2, RefreshCw, Link as LinkIcon
} from 'lucide-react'
import toast from 'react-hot-toast'
import { casesApi, evidenceApi, reportsApi, copilotApi } from '@/api/client'
import type { Case, Evidence, ProcessingStatus } from '@/types'
import { formatDistanceToNow, format } from 'date-fns'
import ForceGraph2D from 'react-force-graph-2d'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar } from 'recharts'
import { useCopilotStore } from '@/stores/copilotStore'

const TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  pdf: FileText, image: Image, video: Video,
  document: File, chat_export: MessageSquare, other: File,
}

const STATUS_CONFIG: Record<ProcessingStatus, { label: string; class: string; icon: React.ComponentType<{ className?: string }> }> = {
  pending: { label: 'Pending', class: 'badge-neutral', icon: Clock },
  processing: { label: 'Processing', class: 'badge-info', icon: Loader2 },
  completed: { label: 'Complete', class: 'badge-low', icon: CheckCircle },
  failed: { label: 'Failed', class: 'badge-critical', icon: X },
  partial: { label: 'Partial', class: 'badge-medium', icon: AlertTriangle },
  duplicate: { label: 'Duplicate', class: 'badge-neutral bg-slate-100 text-slate-600', icon: Copy },
}

const THREAT_CONFIG = {
  critical: 'badge-critical',
  high: 'badge-high',
  medium: 'badge-medium',
  low: 'badge-low',
  informational: 'badge-info',
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}

export default function CasePage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [uploadingFiles, setUploadingFiles] = useState<File[]>([])
  const [activeTab, setActiveTab] = useState<'evidence' | 'entities' | 'timeline' | 'graph' | 'threats' | 'copilot'>('evidence')
  
  // Deletion state
  const [evidenceToDelete, setEvidenceToDelete] = useState<Evidence | null>(null)
  const [evidenceImpact, setEvidenceImpact] = useState<{entities: number, relationships: number, timeline_events: number} | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isDeletingCase, setIsDeletingCase] = useState(false)
  const [showCaseDeleteModal, setShowCaseDeleteModal] = useState(false)

  const deleteCaseMutation = useMutation({
    mutationFn: () => casesApi.delete(caseId!),
    onSuccess: () => {
      toast.success('Case deleted successfully')
      navigate('/cases')
    },
    onError: () => toast.error('Failed to delete case')
  })

  const { data: caseData, isLoading: caseLoading } = useQuery<Case>({
    queryKey: ['case', caseId],
    queryFn: () => casesApi.get(caseId!),
    enabled: !!caseId,
    refetchInterval: 15000,
  })

  const { data: evidence = [], isLoading: evidenceLoading } = useQuery<Evidence[]>({
    queryKey: ['evidence', caseId],
    queryFn: () => evidenceApi.list(caseId!),
    enabled: !!caseId,
    refetchInterval: 8000,
  })

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => evidenceApi.upload(caseId!, files),
    onSuccess: (results) => {
      // Check if any results had duplicate warnings
      results.forEach(r => {
        if (r.message.includes('Warning')) {
          toast(r.message, { icon: '⚠️', duration: 6000 })
        }
      })
      toast.success(`${uploadingFiles.length} file(s) uploaded. Processing started...`)
      setUploadingFiles([])
      queryClient.invalidateQueries({ queryKey: ['evidence', caseId] })
      queryClient.invalidateQueries({ queryKey: ['case', caseId] })
    },
    onError: () => setUploadingFiles([]),
  })

  const reprocessMutation = useMutation({
    mutationFn: (evidenceId: string) => evidenceApi.reprocess(evidenceId),
    onSuccess: () => {
      toast.success('Reprocessing started')
      queryClient.invalidateQueries({ queryKey: ['evidence', caseId] })
    },
    onError: () => toast.error('Failed to start reprocessing')
  })

  const confirmDelete = async (ev: Evidence) => {
    setEvidenceToDelete(ev)
    setEvidenceImpact(null)
    try {
      const impact = await evidenceApi.getImpact(ev.id)
      setEvidenceImpact(impact)
    } catch {
      toast.error('Failed to load impact stats')
    }
  }

  const handleDeleteEvidence = async () => {
    if (!evidenceToDelete) return
    setIsDeleting(true)
    try {
      await evidenceApi.delete(evidenceToDelete.id)
      toast.success('Evidence deleted')
      queryClient.invalidateQueries({ queryKey: ['evidence', caseId] })
      queryClient.invalidateQueries({ queryKey: ['case', caseId] })
      setEvidenceToDelete(null)
    } catch {
      toast.error('Failed to delete evidence')
    } finally {
      setIsDeleting(false)
    }
  }

  const onDrop = useCallback((accepted: File[]) => {
    setUploadingFiles(accepted)
    uploadMutation.mutate(accepted)
  }, [caseId])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'],
      'video/*': ['.mp4', '.avi', '.mov', '.mkv'],
      'text/plain': ['.txt'],
      'application/json': ['.json'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxSize: 500 * 1024 * 1024,
  })

  const downloadReport = async () => {
    try {
      const blob = await reportsApi.generate(caseId!)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `investigation_report_${caseData?.case_number || caseId}.pdf`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Report downloaded!')
    } catch {
      toast.error('Failed to generate report. Ensure backend is running.')
    }
  }

  const tabs = [
    { id: 'evidence', label: 'Evidence', icon: FileText, count: evidence.length },
    { id: 'entities', label: 'Entities', icon: Users, count: caseData?.metrics?.total_entities },
    { id: 'timeline', label: 'Timeline', icon: Calendar, count: caseData?.metrics?.total_timeline_events },
    { id: 'graph', label: 'Relationships', icon: Network, count: caseData?.metrics?.total_relationships },
    { id: 'threats', label: 'Threats', icon: AlertTriangle },
    { id: 'copilot', label: 'Copilot', icon: Bot },
  ]

  if (caseLoading) {
    return (
      <div className="page">
        <div className="animate-pulse space-y-4">
          <div className="skeleton h-10 w-64 rounded-lg" />
          <div className="skeleton h-32 rounded-xl" />
          <div className="skeleton h-64 rounded-xl" />
        </div>
      </div>
    )
  }

  if (!caseData) return null

  const priorityMap = { critical: 'badge-critical', high: 'badge-high', medium: 'badge-medium', low: 'badge-low' }
  const statusMap = { active: 'badge-low', closed: 'badge-neutral', archived: 'badge-neutral', pending_review: 'badge-medium' }

  return (
    <div className="page animate-fade-in">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
        <Link to="/cases" className="hover:text-slate-700 transition-colors flex items-center gap-1">
          <ChevronLeft className="w-4 h-4" /> Cases
        </Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">{caseData.case_number}</span>
      </div>

      {/* Case Header */}
      <div className="card p-6 mb-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className={`badge ${priorityMap[caseData.priority]}`}>
                {caseData.priority.toUpperCase()}
              </span>
              <span className={`badge ${statusMap[caseData.status]}`}>
                {caseData.status.replace('_', ' ').toUpperCase()}
              </span>
              <span className="text-xs text-slate-500 font-mono">{caseData.case_number}</span>
            </div>
            <h1 className="text-2xl font-bold text-slate-900">{caseData.title}</h1>
            {caseData.description && (
              <p className="text-slate-600 mt-1">{caseData.description}</p>
            )}
            <p className="text-xs text-slate-500 mt-2">
              Created {formatDistanceToNow(new Date(caseData.created_at))} ago
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button onClick={() => setShowCaseDeleteModal(true)} className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-colors border border-transparent hover:border-red-100" title="Delete Case">
              <Trash2 className="w-4 h-4" />
            </button>
            <button onClick={downloadReport} className="btn-secondary flex items-center gap-2">
              <Download className="w-4 h-4" /> Export Report
            </button>
          </div>
        </div>

        {/* Metrics Bar */}
        {caseData.metrics && (
          <div className="grid grid-cols-5 gap-3 mt-5 pt-5 border-t border-slate-200/50">
            {[
              { label: 'Evidence Files', value: caseData.metrics.total_evidence, icon: FileText, color: 'text-primary-600' },
              { label: 'Entities', value: caseData.metrics.total_entities, icon: Users, color: 'text-violet-400' },
              { label: 'Timeline Events', value: caseData.metrics.total_timeline_events, icon: Clock, color: 'text-cyan-400' },
              { label: 'Relationships', value: caseData.metrics.total_relationships, icon: Network, color: 'text-emerald-600' },
              { label: 'Processing', value: `${caseData.metrics.investigation_acceleration}%`, icon: TrendingUp, color: 'text-amber-400' },
            ].map(({ label, value, icon: Icon, color }) => (
              <div key={label} className="flex items-center gap-2">
                <Icon className={`w-4 h-4 flex-shrink-0 ${color}`} />
                <div>
                  <div className="font-bold text-slate-900 text-lg leading-tight">{value}</div>
                  <div className="text-xs text-slate-500">{label}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tab Nav */}
      <div className="flex gap-1 p-1 bg-slate-50 rounded-xl border border-slate-200/50 mb-6 overflow-x-auto">
        {tabs.map(({ id, label, icon: Icon, count }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id as any)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
              activeTab === id
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
            {count !== undefined && count > 0 && (
              <span className={`text-xs px-1.5 py-0.5 rounded-full ${activeTab === id ? 'bg-white/20' : 'bg-slate-200 text-slate-600'}`}>
                {count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.15 }}
        >
          {activeTab === 'evidence' && (
            <div className="space-y-4">
              {/* Upload Zone */}
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200 ${
                  isDragActive
                    ? 'border-primary-400 bg-primary-50'
                    : 'border-slate-300/50 hover:border-primary-500/50 hover:bg-primary-500/5'
                }`}
              >
                <input {...getInputProps()} />
                <Upload className={`w-10 h-10 mx-auto mb-3 ${isDragActive ? 'text-primary-600' : 'text-slate-500'}`} />
                {uploadMutation.isPending ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="w-6 h-6 text-primary-600 animate-spin" />
                    <p className="text-slate-600">Uploading {uploadingFiles.length} file(s)...</p>
                  </div>
                ) : isDragActive ? (
                  <p className="text-primary-600 font-medium">Drop to upload evidence files</p>
                ) : (
                  <>
                    <p className="text-slate-700 font-medium mb-1">Drop evidence files here or click to browse</p>
                    <p className="text-slate-500 text-sm">PDF, Images, Video, Documents, Chat exports — up to 500MB each</p>
                    <div className="flex justify-center gap-2 mt-3">
                      {['PDF', 'PNG', 'MP4', 'DOCX', 'JSON'].map(t => (
                        <span key={t} className="badge badge-neutral text-xs">{t}</span>
                      ))}
                    </div>
                  </>
                )}
              </div>

              {/* Evidence Table */}
              {evidenceLoading ? (
                <div className="space-y-2">
                  {[1,2,3].map(i => <div key={i} className="skeleton h-16 rounded-xl" />)}
                </div>
              ) : evidence.length === 0 ? (
                <div className="card p-12 text-center">
                  <FileText className="w-12 h-12 mx-auto mb-3 text-slate-600" />
                  <p className="text-slate-600 font-medium">No evidence uploaded yet</p>
                  <p className="text-slate-500 text-sm mt-1">Drop files above to begin automated processing</p>
                </div>
              ) : (
                <div className="card overflow-hidden">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>File</th>
                        <th>Type</th>
                        <th>Category</th>
                        <th>Size</th>
                        <th>Status</th>
                        <th>Threat</th>
                        <th>Uploaded</th>
                        <th className="text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evidence.map((ev) => {
                        const TypeIcon = TYPE_ICONS[ev.file_type] || File
                        const statusCfg = STATUS_CONFIG[ev.processing_status]
                        const StatusIcon = statusCfg.icon
                        return (
                          <tr key={ev.id}>
                            <td>
                              <div className="flex items-center gap-2">
                                <TypeIcon className="w-4 h-4 text-slate-500 flex-shrink-0" />
                                <span className="font-medium text-slate-800 truncate max-w-[200px]" title={ev.original_filename}>
                                  {ev.original_filename}
                                </span>
                              </div>
                            </td>
                            <td><span className="badge badge-neutral">{ev.file_type.toUpperCase()}</span></td>
                            <td><span className="text-slate-600 capitalize">{ev.category}</span></td>
                            <td><span className="text-slate-600">{formatBytes(ev.size_bytes)}</span></td>
                            <td>
                              <span className={`badge ${statusCfg.class} flex items-center gap-1 w-fit`}>
                                <StatusIcon className={`w-3 h-3 ${ev.processing_status === 'processing' ? 'animate-spin' : ''}`} />
                                {statusCfg.label}
                              </span>
                            </td>
                            <td>
                              <span className={`badge ${THREAT_CONFIG[ev.threat_level]}`}>
                                {ev.threat_level.toUpperCase()}
                              </span>
                            </td>
                            <td>
                              <span className="text-slate-500 text-xs">
                                {formatDistanceToNow(new Date(ev.created_at))} ago
                              </span>
                            </td>
                            <td className="text-right">
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  onClick={() => reprocessMutation.mutate(ev.id)}
                                  disabled={reprocessMutation.isPending}
                                  className="p-1.5 text-slate-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                                  title="Re-run AI Processing"
                                >
                                  <RefreshCw className={`w-4 h-4 ${reprocessMutation.isPending ? 'animate-spin' : ''}`} />
                                </button>
                                <button
                                  onClick={() => confirmDelete(ev)}
                                  className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                  title="Delete Evidence"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Evidence Deletion Modal */}
              <AnimatePresence>
                {evidenceToDelete && (
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
                            Delete Evidence File
                          </h3>
                          <button onClick={() => setEvidenceToDelete(null)} className="text-slate-400 hover:text-slate-600">
                            <X className="w-5 h-5" />
                          </button>
                        </div>
                        
                        <p className="text-slate-600 mb-4">
                          Are you sure you want to delete <strong>{evidenceToDelete.original_filename}</strong>?
                        </p>

                        {!evidenceImpact ? (
                          <div className="flex items-center justify-center py-4 text-slate-500">
                            <Loader2 className="w-5 h-5 animate-spin mr-2" />
                            Calculating destruction impact...
                          </div>
                        ) : (
                          <div className="bg-red-50 border border-red-100 rounded-xl p-4 mb-6">
                            <p className="text-sm font-medium text-red-800 mb-2">This action will permanently destroy:</p>
                            <ul className="space-y-1 text-sm text-red-700">
                              <li className="flex items-center gap-2">
                                <Users className="w-4 h-4" /> <strong>{evidenceImpact.entities}</strong> extracted entities
                              </li>
                              <li className="flex items-center gap-2">
                                <Network className="w-4 h-4" /> <strong>{evidenceImpact.relationships}</strong> relationships
                              </li>
                              <li className="flex items-center gap-2">
                                <Calendar className="w-4 h-4" /> <strong>{evidenceImpact.timeline_events}</strong> timeline events
                              </li>
                            </ul>
                          </div>
                        )}

                        <div className="flex justify-end gap-3 mt-6">
                          <button
                            onClick={() => setEvidenceToDelete(null)}
                            className="btn-secondary"
                            disabled={isDeleting}
                          >
                            Cancel
                          </button>
                          <button
                            onClick={handleDeleteEvidence}
                            className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-xl font-medium transition-colors flex items-center gap-2"
                            disabled={isDeleting || !evidenceImpact}
                          >
                            {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                            Yes, Delete Everything
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          {activeTab === 'entities' && <EntityTab caseId={caseId!} />}
          {activeTab === 'timeline' && <TimelineTab caseId={caseId!} />}
          {activeTab === 'graph' && <GraphTab caseId={caseId!} />}
          {activeTab === 'threats' && <ThreatsTab caseId={caseId!} />}
          {activeTab === 'copilot' && <CopilotTab caseId={caseId!} />}
        </motion.div>
      </AnimatePresence>

      {/* Case Deletion Modal */}
      <AnimatePresence>
        {showCaseDeleteModal && (
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
                  <button onClick={() => setShowCaseDeleteModal(false)} className="text-slate-400 hover:text-slate-600">
                    <X className="w-5 h-5" />
                  </button>
                </div>
                
                <p className="text-slate-600 mb-4">
                  Are you sure you want to delete <strong>{caseData.title}</strong>?
                </p>

                <div className="bg-red-50 border border-red-100 rounded-xl p-4 mb-6">
                  <p className="text-sm font-medium text-red-800 mb-2">This action is irreversible and will destroy:</p>
                  <ul className="space-y-1 text-sm text-red-700">
                    <li className="flex items-center gap-2">
                      <FileText className="w-4 h-4" /> <strong>{caseData.metrics?.total_evidence || 0}</strong> evidence files
                    </li>
                    <li className="flex items-center gap-2">
                      <Users className="w-4 h-4" /> <strong>{caseData.metrics?.total_entities || 0}</strong> extracted entities
                    </li>
                    <li className="flex items-center gap-2">
                      <Network className="w-4 h-4" /> <strong>{caseData.metrics?.total_relationships || 0}</strong> relationships
                    </li>
                    <li className="flex items-center gap-2">
                      <Calendar className="w-4 h-4" /> <strong>{caseData.metrics?.total_timeline_events || 0}</strong> timeline events
                    </li>
                  </ul>
                  <p className="text-xs text-red-600 mt-3 italic text-center border-t border-red-200/50 pt-2">
                    Cross-case links to these entities will also be broken.
                  </p>
                </div>

                <div className="flex justify-end gap-3 mt-6">
                  <button
                    onClick={() => setShowCaseDeleteModal(false)}
                    className="btn-secondary"
                    disabled={deleteCaseMutation.isPending}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => deleteCaseMutation.mutate()}
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

// ── Entity Tab ──────────────────────────────────────────────
function EntityTab({ caseId }: { caseId: string }) {
  const { data: entities = [], isLoading } = useQuery({
    queryKey: ['entities', caseId],
    queryFn: () => evidenceApi.entities(caseId),
  })

  const TYPE_COLORS: Record<string, string> = {
    PERSON: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    ORG: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
    GPE: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    DATE: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    PHONE: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    EMAIL: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    URL: 'bg-slate-500/20 text-slate-600 border-slate-500/30',
    MONEY: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    ID_NUMBER: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    VEHICLE: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
    WEAPON: 'bg-red-500/20 text-red-400 border-red-500/30',
    EVENT: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    OTHER: 'bg-slate-500/20 text-slate-600 border-slate-500/30',
  }

  if (isLoading) return <div className="skeleton h-64 rounded-xl" />

  if (entities.length === 0) {
    return (
      <div className="card p-12 text-center">
        <Users className="w-12 h-12 mx-auto mb-3 text-slate-600" />
        <p className="text-slate-600 font-medium">No entities extracted yet</p>
        <p className="text-slate-500 text-sm mt-1">Upload and process evidence to extract entities</p>
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      <div className="p-4 border-b border-slate-200/50 flex items-center justify-between">
        <h3 className="font-semibold text-slate-900">{entities.length} Entities Detected</h3>
        <div className="text-xs text-slate-500">Sorted by threat relevance</div>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Value</th>
            <th>Frequency</th>
            <th>Confidence</th>
            <th>Threat Score</th>
            <th>Context</th>
          </tr>
        </thead>
        <tbody>
          {[...entities].sort((a, b) => b.threat_relevance - a.threat_relevance).map((entity) => (
            <tr key={entity.id}>
              <td>
                <span className={`badge border ${TYPE_COLORS[entity.entity_type] || TYPE_COLORS.OTHER}`}>
                  {entity.entity_type}
                </span>
              </td>
              <td className="font-mono text-sm text-slate-800 max-w-[200px] truncate">
                <div className="flex items-center gap-2">
                  <span>{entity.value}</span>
                  {entity.cross_case_links && entity.cross_case_links.length > 0 && (
                    <div className="dropdown dropdown-hover dropdown-bottom dropdown-end">
                      <div 
                        tabIndex={0}
                        role="button"
                        className="flex items-center gap-1 px-1.5 py-0.5 bg-indigo-50 border border-indigo-100 text-indigo-600 rounded text-[10px] font-bold tracking-wide transition-colors hover:bg-indigo-100"
                      >
                        <LinkIcon className="w-3 h-3" />
                        MATCH
                      </div>
                      <ul tabIndex={0} className="dropdown-content z-10 menu p-2 shadow-xl bg-white rounded-box w-52 border border-slate-200 mt-1">
                        <li className="menu-title text-xs font-semibold text-slate-500 pb-1">Found in Cases:</li>
                        {entity.cross_case_links.map(link => (
                          <li key={link.id}>
                            <Link to={`/cases/${link.id}`} className="flex flex-col items-start gap-0 py-1.5 px-3 hover:bg-slate-50">
                              <span className="font-medium text-slate-800 text-sm truncate w-full">{link.title}</span>
                              <span className="text-[10px] text-slate-500 font-mono tracking-wider">{link.case_number}</span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </td>
              <td>
                <span className="text-slate-700 font-semibold">{entity.frequency}×</span>
              </td>
              <td>
                <div className="flex items-center gap-2">
                  <div className="progress-bar w-16">
                    <div className="progress-fill" style={{ width: `${entity.confidence * 100}%` }} />
                  </div>
                  <span className="text-xs text-slate-600">{(entity.confidence * 100).toFixed(0)}%</span>
                </div>
              </td>
              <td>
                <div className="flex items-center gap-1">
                  <div className={`w-2 h-2 rounded-full ${entity.threat_relevance > 0.6 ? 'bg-red-400' : entity.threat_relevance > 0.3 ? 'bg-amber-400' : 'bg-emerald-400'}`} />
                  <span className="text-sm">{entity.threat_relevance.toFixed(2)}</span>
                </div>
              </td>
              <td className="text-slate-500 text-xs max-w-[200px] truncate">{entity.context || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Timeline Tab ──────────────────────────────────────────────
function TimelineTab({ caseId }: { caseId: string }) {
  const { data: events = [], isLoading } = useQuery({
    queryKey: ['timeline', caseId],
    queryFn: () => evidenceApi.timeline(caseId),
  })

  const EVENT_ICONS: Record<string, { icon: React.ComponentType<{ className?: string }>; color: string }> = {
    file_created: { icon: File, color: 'text-primary-600 border-primary-100 bg-primary-50' },
    communication_sent: { icon: MessageSquare, color: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10' },
    communication_received: { icon: MessageSquare, color: 'text-violet-400 border-violet-500/30 bg-violet-500/10' },
    location_visit: { icon: Shield, color: 'text-emerald-600 border-emerald-100 bg-emerald-50' },
    transaction: { icon: TrendingUp, color: 'text-amber-400 border-amber-500/30 bg-amber-500/10' },
    entity_mention: { icon: Users, color: 'text-slate-600 border-slate-500/30 bg-slate-500/10' },
    incident: { icon: AlertTriangle, color: 'text-red-400 border-red-500/30 bg-red-500/10' },
    document_signed: { icon: FileText, color: 'text-blue-400 border-blue-500/30 bg-blue-500/10' },
  }

  if (isLoading) return <div className="skeleton h-64 rounded-xl" />

  if (events.length === 0) {
    return (
      <div className="card p-12 text-center">
        <Clock className="w-12 h-12 mx-auto mb-3 text-slate-600" />
        <p className="text-slate-600 font-medium">Timeline not yet reconstructed</p>
        <p className="text-slate-500 text-sm mt-1">Process evidence files to auto-generate timeline</p>
      </div>
    )
  }

  // Group events by Date
  const groupedEvents = events.reduce((acc: any, event: any) => {
    const dateStr = event.event_timestamp ? format(new Date(event.event_timestamp), 'dd MMM yyyy') : 'Unknown Date'
    if (!acc[dateStr]) acc[dateStr] = []
    acc[dateStr].push(event)
    return acc
  }, {})

  // Chart data
  const chartData = Object.keys(groupedEvents).map(date => {
    const dayEvents = groupedEvents[date]
    const breakdown = dayEvents.reduce((acc: any, ev: any) => {
      acc[ev.event_type] = (acc[ev.event_type] || 0) + 1
      return acc
    }, {})
    
    return {
      date,
      events: dayEvents.length,
      breakdown
    }
  })

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-slate-900 border border-slate-700 p-3 rounded-xl shadow-xl z-50 min-w-[150px]">
          <p className="text-slate-400 text-[10px] font-mono mb-2 uppercase tracking-wider">{label}</p>
          <p className="text-white font-bold text-sm mb-2">{data.events} Event{data.events !== 1 && 's'} Recorded</p>
          <div className="space-y-1">
            {Object.entries(data.breakdown).map(([type, count]: [string, any]) => (
              <div key={type} className="flex justify-between items-center gap-4 text-xs">
                <span className="text-slate-300 capitalize">{type.replace(/_/g, ' ')}</span>
                <span className="text-primary-400 font-mono font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-4">
      {/* Activity Heatmap */}
      <div className="card p-5 border border-slate-200">
        <div className="section-label mb-2">Event Frequency</div>
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="date" hide />
              <YAxis hide />
              <Tooltip 
                content={<CustomTooltip />}
                cursor={{ fill: 'rgba(59, 130, 246, 0.05)' }}
              />
              <Bar 
                dataKey="events" 
                fill="#3b82f6" 
                radius={[4, 4, 0, 0]} 
                animationDuration={1500}
                animationEasing="ease-out"
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={index % 2 === 0 ? '#3b82f6' : '#60a5fa'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Grouped Timeline */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-900">{events.length} Timeline Events</h3>
          <span className="text-xs text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md border border-slate-200">Chronological order</span>
        </div>
        
        <div className="max-h-[400px] overflow-y-auto pr-2">
          {Object.entries(groupedEvents).map(([date, dayEvents]: [string, any]) => (
            <div key={date} className="mb-4">
              <div className="badge bg-slate-800 text-white font-mono text-[10px] uppercase tracking-wider mb-3">{date}</div>
              <div className="border-l-2 border-slate-200 ml-3 pl-4 space-y-4">
                {dayEvents.map((event: any) => {
                  const cfg = EVENT_ICONS[event.event_type] || EVENT_ICONS.entity_mention
                  return (
                    <div key={event.id} className="relative">
                      <div className="absolute -left-[1.35rem] top-1 w-2.5 h-2.5 rounded-full bg-white border-2 border-primary-500"></div>
                      <div>
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold text-slate-800 text-xs leading-none">{event.title}</h4>
                          {event.event_timestamp && (
                            <span className="text-[10px] font-mono text-slate-500">{format(new Date(event.event_timestamp), 'HH:mm')}</span>
                          )}
                        </div>
                        {event.description && (
                          <p className="text-[11px] text-slate-500 mt-1 leading-snug">{event.description}</p>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Graph Tab ──────────────────────────────────────────────
function GraphTab({ caseId }: { caseId: string }) {
  const fgRef = useRef<any>()

  const { data: graph, isLoading } = useQuery({
    queryKey: ['graph', caseId],
    queryFn: () => evidenceApi.graph(caseId),
  })

  useEffect(() => {
    // Increase repulsive charge and link distance so nodes don't cluster on top of each other
    if (fgRef.current && graph) {
      fgRef.current.d3Force('charge').strength(-600)
      fgRef.current.d3Force('link').distance(120)
    }
  }, [graph])

  if (isLoading) return <div className="skeleton h-64 rounded-xl" />

  if (!graph || graph.total_nodes === 0) {
    return (
      <div className="card p-12 text-center">
        <Network className="w-12 h-12 mx-auto mb-3 text-slate-600" />
        <p className="text-slate-600 font-medium">Relationship graph not built yet</p>
        <p className="text-slate-500 text-sm mt-1">Entity extraction must complete first</p>
      </div>
    )
  }

  const GROUP_COLORS: Record<number, string> = {
    1: '#3b82f6', 2: '#8b5cf6', 3: '#10b981', 4: '#f59e0b',
    5: '#06b6d4', 6: '#64748b', 7: '#10b981', 8: '#f97316',
    9: '#ef4444', 10: '#dc2626', 0: '#64748b',
  }

  const graphData = {
    nodes: graph.nodes.map((n: any) => ({ ...n, val: Math.min(10, 4 + n.frequency) })),
    links: graph.edges.map((e: any) => ({ source: e.source, target: e.target, name: e.relationship_type, value: e.weight }))
  }

  // Get unique groups for legend
  const uniqueGroups = Array.from(new Set(graph.nodes.map((n: any) => n.group)))
  const getGroupName = (group: number) => {
    const node = graph.nodes.find((n: any) => n.group === group)
    return node ? node.entity_type : 'Unknown'
  }

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Nodes', value: graph.total_nodes, icon: Users },
          { label: 'Connections', value: graph.total_edges, icon: Network },
          { label: 'Communities', value: graph.communities, icon: Shield },
        ].map(({ label, value, icon: Icon }) => (
          <div key={label} className="card p-4 flex items-center gap-3">
            <Icon className="w-5 h-5 text-primary-600" />
            <div>
              <div className="text-xl font-bold text-slate-900">{value}</div>
              <div className="text-xs text-slate-500">{label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="card overflow-hidden bg-slate-50 relative border-slate-200 shadow-sm" style={{ height: 650, width: '100%' }}>
        {/* Floating Legend */}
        <div className="absolute top-4 left-4 bg-white/95 backdrop-blur shadow-sm border border-slate-200 rounded-xl p-3 z-10 pointer-events-none">
          <div className="text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-widest">Entity Types</div>
          <div className="space-y-1.5">
            {uniqueGroups.slice(0, 8).map((g: any) => (
              <div key={g} className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: GROUP_COLORS[g] || GROUP_COLORS[0] }} />
                <span className="text-xs text-slate-700 font-medium">{getGroupName(g)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Floating Tool Bar (Static visual) */}
        <div className="absolute top-4 right-4 bg-white/95 backdrop-blur shadow-sm border border-slate-200 rounded-xl p-1.5 z-10 flex flex-col gap-1">
          <button className="p-2 hover:bg-slate-100 rounded-lg text-slate-600 transition-colors" title="Zoom In">
             <div className="w-4 h-0.5 bg-current absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
             <div className="w-0.5 h-4 bg-current absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
          </button>
          <div className="w-full h-px bg-slate-200 my-0.5" />
          <button className="p-2 hover:bg-slate-100 rounded-lg text-slate-600 transition-colors" title="Zoom Out">
             <div className="w-4 h-0.5 bg-current absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
          </button>
        </div>

        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          width={1000}
          height={650}
          backgroundColor="#f8fafc"
          linkDirectionalArrowLength={3.5}
          linkDirectionalArrowRelPos={1}
          linkCurvature={0.2}
          linkColor={() => '#cbd5e1'}
          linkWidth={(link: any) => Math.max(1, link.value * 0.4)}
          nodeRelSize={6}
          onNodeClick={(node: any) => toast.success(`Analyzed ${node.entity_type}: ${node.label}`)}
          nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
            const label = node.label || ''
            const r = node.val || 5

            // Draw Node Shadow
            ctx.shadowColor = 'rgba(0,0,0,0.1)'
            ctx.shadowBlur = 10 / globalScale
            ctx.shadowOffsetY = 2 / globalScale

            // Draw Node Circle
            ctx.beginPath()
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false)
            ctx.fillStyle = GROUP_COLORS[node.group] || GROUP_COLORS[0]
            ctx.fill()
            
            // Draw Node Border
            ctx.shadowColor = 'transparent'
            ctx.lineWidth = 1.5 / globalScale
            ctx.strokeStyle = '#ffffff'
            ctx.stroke()

            // Draw Label
            // We only hide labels if zoomed WAY out, otherwise always show since we have space now
            if (globalScale > 0.6) {
              const fontSize = 11 / globalScale
              ctx.font = `600 ${fontSize}px Inter, sans-serif`
              ctx.textAlign = 'center'
              ctx.textBaseline = 'top'
              
              // White halo for text readability
              ctx.lineWidth = 3 / globalScale
              ctx.strokeStyle = 'rgba(255, 255, 255, 0.95)'
              ctx.lineJoin = 'round'
              ctx.strokeText(label, node.x, node.y + r + (4 / globalScale))
              
              ctx.fillStyle = '#1e293b'
              ctx.fillText(label, node.x, node.y + r + (4 / globalScale))
              
              // Draw Type pill
              const typeFontSize = 8 / globalScale
              ctx.font = `500 ${typeFontSize}px Inter, sans-serif`
              ctx.strokeText(node.entity_type, node.x, node.y + r + (4 / globalScale) + fontSize * 1.2)
              ctx.fillStyle = '#64748b'
              ctx.fillText(node.entity_type, node.x, node.y + r + (4 / globalScale) + fontSize * 1.2)
            }
          }}
          linkCanvasObjectMode={() => 'after'}
          linkCanvasObject={(link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
            if (globalScale < 2) return // Only show link labels when zoomed in
            
            const MAX_FONT_SIZE = 4
            const LABEL_NODE_MARGIN = link.source.val * 1.5
            
            const start = link.source
            const end = link.target
            
            // ignore unbound links
            if (typeof start !== 'object' || typeof end !== 'object') return
            
            // calculate label positioning
            const textPos = Object.assign(
              ...['x', 'y'].map(c => ({
                [c]: start[c] + (end[c] - start[c]) / 2 // calc middle point
              }))
            )
            
            const relLink = { x: end.x - start.x, y: end.y - start.y }
            let textAngle = Math.atan2(relLink.y, relLink.x)
            // maintain label vertical orientation
            if (textAngle > Math.PI / 2) textAngle = -(Math.PI - textAngle)
            if (textAngle < -Math.PI / 2) textAngle = -(-Math.PI - textAngle)
            
            const label = link.name.replace('_', ' ')
            
            ctx.font = `500 ${Math.max(10/globalScale, 2)}px Inter, sans-serif`
            const textWidth = ctx.measureText(label).width
            const bckgDimensions = [textWidth, Math.max(10/globalScale, 2)].map(n => n + (2/globalScale)) // some padding
            
            // draw text bounding box
            ctx.translate(textPos.x, textPos.y)
            ctx.rotate(textAngle)
            
            ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
            ctx.beginPath()
            ctx.roundRect(-bckgDimensions[0] / 2, -bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1], 2/globalScale)
            ctx.fill()
            
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            ctx.fillStyle = '#64748b'
            ctx.fillText(label, 0, 0)
            
            ctx.rotate(-textAngle)
            ctx.translate(-textPos.x, -textPos.y)
          }}
        />
      </div>
    </div>
  )
}

// ── Threats Tab ──────────────────────────────────────────────
function ThreatsTab({ caseId }: { caseId: string }) {
  const { data: threats, isLoading } = useQuery({
    queryKey: ['threats', caseId],
    queryFn: () => evidenceApi.threats(caseId),
  })

  const { data: entities = [] } = useQuery({
    queryKey: ['entities', caseId],
    queryFn: () => evidenceApi.entities(caseId),
  })

  if (isLoading) return <div className="skeleton h-64 rounded-xl" />

  const LEVEL_CONFIG: Record<string, { class: string; bg: string; border: string }> = {
    critical: { class: 'badge-critical', bg: 'bg-red-500/5', border: 'border-red-500/20' },
    high: { class: 'badge-high', bg: 'bg-orange-500/5', border: 'border-orange-500/20' },
    medium: { class: 'badge-medium', bg: 'bg-amber-500/5', border: 'border-amber-500/20' },
    low: { class: 'badge-low', bg: 'bg-emerald-50', border: 'border-emerald-100' },
    informational: { class: 'badge-info', bg: 'bg-blue-500/5', border: 'border-blue-500/20' },
  }

  if (!threats || threats.insights.length === 0) {
    return (
      <div className="card p-12 text-center">
        <Shield className="w-12 h-12 mx-auto mb-3 text-emerald-600" />
        <p className="text-slate-600 font-medium">No threat indicators detected</p>
        <p className="text-slate-500 text-sm mt-1">Process evidence to generate threat intelligence</p>
      </div>
    )
  }

  const overallCfg = LEVEL_CONFIG[threats.overall_threat_level] || LEVEL_CONFIG.informational

  const distributionData = [
    { name: 'Critical', value: threats.total_critical, fill: '#ef4444' },
    { name: 'High', value: threats.total_high, fill: '#f97316' },
    { name: 'Medium', value: threats.total_medium, fill: '#f59e0b' },
    { name: 'Low', value: threats.total_low, fill: '#10b981' },
  ]

  // Gauge chart data
  const score = Math.round(threats.overall_threat_score * 100)
  const gaugeData = [
    { name: 'Score', value: score, fill: overallCfg.color },
    { name: 'Remainder', value: 100 - score, fill: '#f1f5f9' },
  ]

  return (
    <div className="space-y-4">
      {/* Visual Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Gauge Chart */}
        <div className={`card p-5 border ${overallCfg.border} ${overallCfg.bg} flex flex-col justify-between h-[200px]`}>
          <div className="section-label mb-2">Overall Assessment</div>
          <div className="relative flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={gaugeData}
                  cx="50%"
                  cy="100%"
                  startAngle={180}
                  endAngle={0}
                  innerRadius={65}
                  outerRadius={85}
                  dataKey="value"
                  stroke="none"
                  cornerRadius={4}
                >
                  {gaugeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex flex-col items-center justify-end pb-1 pointer-events-none">
              <span className="text-4xl font-bold text-slate-900 leading-none">{score}</span>
              <span className={`badge mt-2 ${overallCfg.class}`}>{threats.overall_threat_level.toUpperCase()}</span>
            </div>
          </div>
        </div>

        {/* Distribution Bar Chart */}
        <div className="card p-5 border border-slate-200 md:col-span-2 h-[200px] flex flex-col">
          <div className="section-label mb-2">Threat Distribution</div>
          <div className="flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={distributionData} layout="vertical" margin={{ top: 0, right: 30, left: 10, bottom: 0 }}>
                <XAxis type="number" hide />
                <YAxis dataKey="name" type="category" width={65} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12, fontWeight: 500 }} />
                <Tooltip 
                  cursor={{ fill: 'rgba(0,0,0,0.02)' }}
                  contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20} label={{ position: 'right', fill: '#475569', fontSize: 12, fontWeight: 600 }}>
                  {distributionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Insight Cards */}
      <div className="space-y-3">
        {threats.insights.map((insight) => {
          const cfg = LEVEL_CONFIG[insight.threat_level] || LEVEL_CONFIG.informational
          return (
            <motion.div
              key={insight.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`card p-5 border ${cfg.border} ${cfg.bg}`}
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-semibold text-slate-900">{insight.title}</h3>
                    <p className="text-sm text-slate-600 mt-1">{insight.description}</p>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2 flex-shrink-0">
                  <span className={`badge ${cfg.class}`}>{insight.threat_level.toUpperCase()}</span>
                  <span className="text-xs text-slate-500">Score: {(insight.threat_score * 100).toFixed(0)}</span>
                </div>
              </div>
              <div className="flex items-start gap-2 p-3 rounded-lg bg-surface-100/50 border border-slate-200/30">
                <Shield className="w-4 h-4 text-primary-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-slate-700">{insight.recommendation}</p>
              </div>
              <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                <div className="relative group cursor-pointer">
                  <span className="border-b border-dashed border-slate-400 pb-0.5">
                    {insight.entity_ids.length} entities involved
                  </span>
                  
                  {/* Tooltip */}
                  {insight.entity_ids.length > 0 && (
                    <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block w-max max-w-xs bg-slate-800 text-slate-200 text-xs rounded-lg shadow-xl border border-slate-700 p-2.5 z-50">
                      <div className="font-semibold text-white mb-1.5 border-b border-slate-700 pb-1">Involved Entities</div>
                      <div className="space-y-1">
                        {insight.entity_ids.map((id: string) => {
                          const entity = entities.find((e: any) => e.id === id)
                          return (
                            <div key={id} className="flex items-center justify-between gap-3">
                              <span className="truncate">{entity?.value || id}</span>
                              <span className="text-[10px] text-slate-400 bg-slate-700 px-1.5 py-0.5 rounded uppercase tracking-wider">{entity?.entity_type || 'UNKNOWN'}</span>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
                <span>•</span>
                <span>Confidence: {(insight.confidence * 100).toFixed(0)}%</span>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

// ── Copilot Tab ──────────────────────────────────────────────
function CopilotTab({ caseId }: { caseId: string }) {
  const { queries, histories, loadingStates, setQuery, addHistory, setLoading } = useCopilotStore()
  
  const query = queries[caseId] || ''
  const history = histories[caseId] || []
  const loading = loadingStates[caseId] || false

  const queryMutation = useMutation({
    mutationFn: (q: string) => copilotApi.query(caseId, q),
  })


  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    const q = query
    setQuery(caseId, '')
    setLoading(caseId, true)
    try {
      const historyPayload = history.map(h => ({
        user: h.q,
        assistant: h.r.response
      }))

      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/cases/${caseId}/copilot/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('iip-auth') ? JSON.parse(localStorage.getItem('iip-auth')!).state?.accessToken : ''}` },
        body: JSON.stringify({ query: q, history: historyPayload }),
      })
      const data = await res.json()
      addHistory(caseId, { q, r: data })
    } catch {
      toast.error('Copilot query failed')
    } finally {
      setLoading(caseId, false)
    }
  }

  const SUGGESTIONS = [
    'Summarize the key findings from this case',
    'Who are the persons of interest?',
    'What are the recommended next investigation steps?',
    'Identify any financial crime indicators',
  ]

  return (
    <div className="space-y-4">
      <div className="card p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg bg-primary-50 border border-primary-100">
            <Bot className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">Investigation Copilot</h3>
            <p className="text-xs text-slate-500">AI-powered insights grounded in your evidence</p>
          </div>
        </div>

        {/* Suggestions */}
        {history.length === 0 && (
          <div className="grid grid-cols-2 gap-2 mb-4">
            {SUGGESTIONS.map(s => (
              <button
                key={s}
                onClick={() => setQuery(caseId, s)}
                className="text-left p-3 rounded-lg border border-slate-200/50 hover:border-primary-100 
                           hover:bg-primary-500/5 text-sm text-slate-600 hover:text-slate-800 transition-all duration-150"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* History */}
        {history.map((item, i) => (
          <div key={i} className="mb-4 space-y-3">
            <div className="flex justify-end">
              <div className="max-w-[80%] p-3 rounded-xl rounded-tr-sm bg-primary-600/20 border border-primary-100">
                <p className="text-sm text-slate-800">{item.q}</p>
              </div>
            </div>
            <div className="flex justify-start">
              <div className="max-w-[90%] p-4 rounded-xl rounded-tl-sm bg-surface-100 border border-slate-200/50">
                <div className="flex items-center gap-2 mb-2">
                  <Bot className="w-4 h-4 text-primary-600" />
                  <span className="text-xs text-slate-500 font-mono">{item.r.model_used}</span>
                  <span className="text-xs text-slate-600">•</span>
                  <span className="text-xs text-slate-500">{(item.r.confidence * 100).toFixed(0)}% confidence</span>
                </div>
                <div className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{item.r.response}</div>
                {item.r.sources?.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-200/50">
                    <div className="text-xs text-slate-500 mb-1.5">Sources:</div>
                    {item.r.sources.map((src: any, j: number) => (
                      <div key={j} className="text-xs text-slate-500 flex items-center gap-1.5 mb-1">
                        <FileText className="w-3 h-3 flex-shrink-0" />
                        <span className="font-medium text-slate-600">{src.filename}</span>
                        <span className="text-slate-600">— {src.snippet.slice(0, 60)}…</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start mb-4">
            <div className="p-4 rounded-xl rounded-tl-sm bg-surface-100 border border-slate-200/50 flex items-center gap-2">
              <Loader2 className="w-4 h-4 text-primary-600 animate-spin" />
              <span className="text-sm text-slate-600">Analyzing evidence...</span>
            </div>
          </div>
        )}

        {/* Input */}
        <form onSubmit={handleQuery} className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(caseId, e.target.value)}
            placeholder="Ask about this case..."
            className="input flex-1"
            disabled={loading}
          />
          <button type="submit" disabled={loading || !query.trim()} className="btn-primary px-4 flex-shrink-0">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          </button>
        </form>
      </div>
    </div>
  )
}
