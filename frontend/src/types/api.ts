export interface ApiResponse<T> {
  code: string
  message: string
  data: T
}

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export interface ProjectRankingItem {
  project_id: string
  project_name: string
  total_risk_score: number
  risk_level: RiskLevel
}

export interface DashboardOverview {
  total_projects: number
  high_risk_projects: number
  critical_risk_projects?: number
  open_work_orders: number
  overdue_work_orders: number
  high_risk_workers?: number
  project_ranking: ProjectRankingItem[]
  work_order_status?: Array<{ status: string; count: number }>
  recent_rule_triggers?: Array<{
    rule_id: string
    object_type: string
    object_id: string
    project_id: string
    severity: string
    created_at: string
  }>
}

export interface ProfileData {
  project_id?: string
  worker_id?: string
  subcontractor_id?: string
  calc_date: string
  total_risk_score: number
  risk_level: RiskLevel
  data_completeness: number | null
  risk_tags: { tags: string[] } | null
  explanation: string | null
  suggestion: string | null
  project_name?: string | null
  project_type?: string | null
  worker_name_masked?: string | null
  subcontractor_name?: string | null
  confidence_level?: string | null
  dimension_scores?: Record<string, number | null>
}

export interface WorkOrder {
  work_order_id: string
  work_order_type: string
  title: string | null
  description: string | null
  project_id: string | null
  project_name?: string | null
  subcontractor_id?: string | null
  worker_id?: string | null
  status: string
  priority: string
  due_time: string | null
  escalation_level: number
  rule_id?: string | null
  created_at: string
}

export interface AssistantResult {
  available: boolean
  message: string
  content: string | null
}
