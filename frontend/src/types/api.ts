export interface ApiResponse<T> {
  code: string
  message: string
  data: T
}

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'
export type ScopeType = 'company' | 'project'
export type DataScope = 'tenant' | 'org'

export interface CurrentUser {
  user_id: string
  user_name: string
  tenant_id: string
  company_id: string
  org_path: string
  role: string
  data_scope: DataScope
  scope_type: ScopeType
  authorized_project_ids: string[]
  roles?: string[]
  permissions?: string[]
  auth_source?: string
  subcontractor_id?: string | null
}

export interface AuthTokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: CurrentUser
  oauth?: {
    mode: string
    state?: string | null
    provider?: string
  }
}

export interface OAuthAuthorizeResult {
  mode: 'mock' | 'live' | 'disabled'
  state: string
  authorize_url: string
  callback_path?: string
  redirect_uri?: string
  message: string
}

export interface ProjectListItem {
  project_id: string
  project_name: string
}

export interface ProjectListResponse {
  items: ProjectListItem[]
}

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
  calculated_at: string
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
  overdue_rectification_ratio?: number | null
}

export interface WorkOrder {
  work_order_id: string
  work_order_type: string
  source_type?: string | null
  source_id?: string | null
  title: string | null
  description: string | null
  project_id: string | null
  project_name?: string | null
  subcontractor_id?: string | null
  worker_id?: string | null
  equipment_id?: string | null
  status: string
  priority: string
  responsible_user_id?: string | null
  review_user_id?: string | null
  due_time: string | null
  review_time?: string | null
  close_time?: string | null
  reject_reason?: string | null
  escalation_level: number
  rule_id?: string | null
  attachments?: WorkOrderAttachmentEnvelope | null
  created_at: string
}

export interface WorkOrderAttachment {
  file_id: string
  file_name?: string | null
  content_type?: string | null
  size_bytes?: number | null
  sha256?: string | null
  phase?: string | null
  uploaded_by?: string | null
  uploaded_at?: string | null
  url?: string | null
}

export interface WorkOrderAttachmentEnvelope {
  items?: WorkOrderAttachment[]
}

export interface WorkOrderFlowLog {
  from_status: string | null
  to_status: string
  action: string
  operator_user_id: string
  operator_role: string
  comment: string | null
  reject_reason: string | null
  attachments?: WorkOrderAttachmentEnvelope | null
  created_at: string
}

export interface WorkOrderDetail extends WorkOrder {
  flow_logs: WorkOrderFlowLog[]
}

export interface WorkOrderStatusPayload {
  action: string
  comment?: string | null
  assignee_user_id?: string | null
  due_time?: string | null
  reject_reason?: string | null
  attachments?: WorkOrderAttachmentEnvelope | null
}

export interface WorkOrderCreatePayload {
  work_order_type: string
  title: string
  description?: string | null
  project_id?: string | null
  priority?: string
}

export interface HazardCreateResult {
  hazard_id: string
  work_order_id: string
  work_order_status?: string
  attachments?: WorkOrderAttachment[]
}

export interface AssistantResult {
  available: boolean
  message: string
  content: string | null
  need_human_review?: boolean
}

export interface MetricCatalogItem {
  metric_code: string
  metric_name: string
  business_definition: string | null
  statistical_period: string | null
  permission_level: string | null
  metric_version: string
  status: string
}

export interface MetricDetail extends MetricCatalogItem {
  calculation_formula?: string | null
  dimensions?: unknown
  source_tables?: unknown
  source_fields?: unknown
  filters?: unknown
  aliases?: string[] | null
  owner_department?: string | null
}

export interface MetricCatalogPage {
  page_no: number
  page_size: number
  total: number
  items: MetricCatalogItem[]
}

export type AgentApprovalStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'executed'
  | 'execution_failed'
  | 'expired'

export interface AgentApprovalRequest {
  approval_id: string
  run_id: string | null
  step_run_id: string | null
  company_id: string | null
  project_id: string | null
  scope_type: string | null
  request_user_id: string | null
  requested_tool: string
  requested_action: string | null
  target_type: string | null
  target_id: string | null
  payload_summary: string | null
  payload_json: Record<string, unknown> | null
  risk_level: string | null
  reason: string | null
  evidence_refs: unknown[] | null
  status: AgentApprovalStatus | string
  approver_user_id: string | null
  approval_comment: string | null
  executor_user_id: string | null
  executed_at: string | null
  execution_result: Record<string, unknown> | null
  execution_error: string | null
  created_at: string | null
  updated_at: string | null
  approved_at: string | null
  rejected_at: string | null
  expires_at: string | null
}

export interface AgentApprovalList {
  items: AgentApprovalRequest[]
  total: number
}

export interface AgentAskStepResult {
  step_id: string
  agent_code: string
  action?: string | null
  tool_name?: string | null
  status: string
  approval_id?: string | null
  output_summary?: Record<string, unknown> | null
}

export interface Nl2SqlQueryResult {
  status: string
  audit_id: string | null
  question: string
  allowed: boolean
  sanitized_sql: string | null
  execution_status: string
  row_count: number
  field_count: number
  columns: string[]
  rows: Array<Record<string, unknown>>
  execution_error?: string | null
  rejection_reason?: string | null
  tables_used: string[]
  fields_used: string[]
  scope_injected: boolean
  need_human_review?: boolean
  clarification_id?: string | null
  clarification_prompt?: string | null
  awaiting_clarification?: boolean
  turn?: number
  refined_question?: string | null
  session_id?: string
}

export interface AgentFeedbackItem {
  feedback_id: string
  task_id: string
  company_id: string | null
  project_id: string | null
  user_id: string
  agent_name: string
  feedback_type: 'thumb' | 'rating' | 'correction' | 'adoption'
  rating: number | null
  feedback_reason: string | null
  original_output: Record<string, unknown> | null
  corrected_output: Record<string, unknown> | null
  correction_text: string | null
  related_work_order_id: string | null
  label_status: string
  used_for_prompt_tuning: boolean
  used_for_finetune: boolean
  created_at: string | null
}

export interface AgentFeedbackList {
  items: AgentFeedbackItem[]
  total: number
}

export interface AgentAskResult {
  target_agent: string
  intent?: string
  execution_mode?: string
  prompt_version?: string
  need_human_review?: boolean
  dag_status?: string
  dag_execution_allowed?: boolean
  step_results?: AgentAskStepResult[]
  run_id?: string
  preview_status?: string
  llm_available?: boolean
  session_id?: string
  memory_source?: string
  blocked_reason?: string | null
  context?: Record<string, unknown>
}

export interface RuleTriggerLog {
  trigger_id: string
  project_id: string | null
  object_type: string
  object_id: string
  rule_id: string
  rule_name: string
  severity: string
  evidence: unknown
  created_at: string
}

export interface ProjectWeeklyReportPeriod {
  start_date: string
  end_date: string
  week_label: string
}

export interface ProjectWeeklyReportKpi {
  total_risk_score: number | null
  risk_level: RiskLevel | null
  open_hazards: number
  major_hazards_open: number
  overdue_hazards: number
  open_work_orders: number
  overdue_work_orders: number
  week_new_work_orders: number
  rule_triggers_count: number
  high_risk_workers: number
  equipment_overdue_count: number
}

export interface ProjectWeeklyReportRuleTrigger {
  trigger_id: string
  rule_id: string
  rule_name: string
  severity: string
  object_type: string
  object_id: string
  evidence: unknown
  created_at: string
}

export interface ProjectWeeklyReportWorkOrder {
  work_order_id: string
  work_order_type: string
  title: string
  status: string
  priority: string
  rule_id: string | null
  due_time: string | null
  created_at: string
}

export interface ProjectWeeklyReport {
  report_id: string
  report_type: 'project_weekly'
  tenant_id: string
  project_id: string
  project_name: string
  period: ProjectWeeklyReportPeriod
  generated_at: string
  kpi: ProjectWeeklyReportKpi
  rule_triggers: ProjectWeeklyReportRuleTrigger[]
  work_orders: ProjectWeeklyReportWorkOrder[]
  highlights: string[]
  evidence_refs: Array<{ type: string; id: string; rule_id?: string | null }>
}

export interface SubcontractorEvalDimensionScores {
  qualification_risk: number | null
  worker_management: number | null
  hazard_rectification: number | null
  violation_risk: number | null
  equipment_management: number | null
  accident_credit: number | null
}

export interface SubcontractorEvalProfile {
  calc_date: string | null
  total_risk_score: number | null
  risk_level: RiskLevel | null
  eval_grade: string
  data_completeness: number | null
  dimension_scores: SubcontractorEvalDimensionScores | null
  explanation: string | null
}

export interface SubcontractorEvalKpi {
  total_risk_score: number | null
  risk_level: RiskLevel | null
  eval_grade: string
  active_workers: number
  high_risk_workers: number
  open_hazards: number
  overdue_hazards: number
  major_hazards_open: number
  open_work_orders: number
  violations_30d: number
  accident_history_count: number
  credit_score: number | null
  safety_license_status: string | null
  high_risk_worker_ratio: number | null
  overdue_rectification_ratio: number | null
}

export interface SubcontractorEvalHazard {
  hazard_id: string
  hazard_type: string
  hazard_level: string
  status: string
  due_date: string | null
  is_major: boolean
  description: string | null
}

export interface SubcontractorEvalWorkOrder {
  work_order_id: string
  title: string
  status: string
  priority: string
  rule_id: string | null
  due_time: string | null
}

export interface SubcontractorEvalWorker {
  worker_id: string
  worker_name_masked: string
  work_type: string
  violation_count_30d: number
  special_cert_status: string | null
}

export interface SubcontractorEvalReport {
  report_id: string
  report_type: 'subcontractor_eval'
  tenant_id: string
  subcontractor_id: string
  subcontractor_name: string
  project_id: string | null
  project_name: string | null
  eval_date: string
  generated_at: string
  profile: SubcontractorEvalProfile
  kpi: SubcontractorEvalKpi
  hazards: SubcontractorEvalHazard[]
  work_orders: SubcontractorEvalWorkOrder[]
  workers_summary: SubcontractorEvalWorker[]
  highlights: string[]
  recommendations: string[]
  evidence_refs: Array<{ type: string; id: string; rule_id?: string | null }>
}
