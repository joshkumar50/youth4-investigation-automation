// All TypeScript interfaces and types for the platform

export type UserRole = 'admin' | 'supervisor' | 'investigator'
export type CaseStatus = 'active' | 'closed' | 'archived' | 'pending_review'
export type CasePriority = 'critical' | 'high' | 'medium' | 'low'
export type EvidenceType = 'pdf' | 'image' | 'video' | 'document' | 'chat_export' | 'audio' | 'other'
export type EvidenceCategory = 'communication' | 'financial' | 'location' | 'identity' | 'media' | 'legal' | 'threat' | 'other'
export type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'partial' | 'duplicate'
export type EntityType = 'PERSON' | 'ORG' | 'GPE' | 'DATE' | 'PHONE' | 'EMAIL' | 'URL' | 'MONEY' | 'ID_NUMBER' | 'VEHICLE' | 'WEAPON' | 'EVENT' | 'OTHER'
export type ThreatLevel = 'critical' | 'high' | 'medium' | 'low' | 'informational'
export type EventType = 'file_created' | 'communication_sent' | 'communication_received' | 'location_visit' | 'transaction' | 'entity_mention' | 'incident' | 'document_signed'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface CaseMetrics {
  total_evidence: number
  processed_evidence: number
  pending_evidence: number
  total_entities: number
  total_timeline_events: number
  total_relationships: number
  processing_duration_seconds: number | null
  investigation_acceleration: number
  threat_score_average: number
}

export interface Case {
  id: string
  title: string
  description: string | null
  case_number: string
  status: CaseStatus
  priority: CasePriority
  tags: string[] | null
  created_by: string
  created_at: string
  updated_at: string
  metrics: CaseMetrics | null
}

export interface CaseListResponse {
  items: Case[]
  total: number
  page: number
  page_size: number
}

export interface Evidence {
  id: string
  case_id: string
  filename: string
  original_filename: string
  file_type: EvidenceType
  category: EvidenceCategory
  category_confidence: number
  size_bytes: number
  mime_type: string | null
  processing_status: ProcessingStatus
  processing_error: string | null
  threat_level: ThreatLevel
  threat_score: number
  uploaded_by: string
  created_at: string
  processed_at: string | null
  extraction_metadata: Record<string, unknown> | null
}

export interface EvidenceUploadResponse {
  evidence_id: string
  filename: string
  size_bytes: number
  processing_status: ProcessingStatus
  task_id: string
  message: string
}

export interface EvidenceStatus {
  evidence_id: string
  processing_status: ProcessingStatus
  progress_percent: number
  current_stage: string
  processing_error: string | null
  estimated_completion_seconds: number | null
}

export interface CrossCaseLink {
  id: string;
  title: string;
  case_number: string;
}

export interface Entity {
  id: string
  case_id: string
  evidence_id: string
  entity_type: EntityType
  value: string
  normalized_value: string
  confidence: number
  frequency: number
  context: string | null
  is_primary: boolean
  threat_relevance: number
  created_at: string
  cross_case_links: CrossCaseLink[]
}

export interface TimelineEvent {
  id: string
  case_id: string
  evidence_id: string | null
  entity_id: string | null
  event_type: EventType
  title: string
  description: string | null
  event_timestamp: string | null
  confidence: number
  created_at: string
}

export interface GraphNode {
  id: string
  label: string
  entity_type: EntityType
  frequency: number
  threat_relevance: number
  is_primary: boolean
  group: number
}

export interface GraphEdge {
  source: string
  target: string
  relationship_type: string
  weight: number
  evidence_count: number
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_nodes: number
  total_edges: number
  communities: number
}

export interface ThreatInsight {
  id: string
  title: string
  description: string
  threat_level: ThreatLevel
  threat_score: number
  entity_ids: string[]
  evidence_ids: string[]
  recommendation: string
  confidence: number
}

export interface ThreatResponse {
  case_id: string
  overall_threat_level: ThreatLevel
  overall_threat_score: number
  insights: ThreatInsight[]
  total_critical: number
  total_high: number
  total_medium: number
  total_low: number
}

export interface CopilotSource {
  evidence_id: string
  filename: string
  snippet: string
  relevance_score: number
}

export interface CopilotResponse {
  query: string
  response: string
  sources: CopilotSource[]
  generated_at: string
  model_used: string
  confidence: number
}

export interface DashboardMetrics {
  total_cases: number
  active_cases: number
  total_evidence_files: number
  total_entities_detected: number
  total_processing_time_saved_hours: number
  files_processed_today: number
  average_case_resolution_hours: number
  cases_by_priority: Record<string, number>
  cases_by_status: Record<string, number>
  evidence_by_type: Record<string, number>
  evidence_by_category: Record<string, number>
  recent_activity: Record<string, unknown>[]
}
