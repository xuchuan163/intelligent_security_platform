import axios from 'axios'

import {
  clearAuthSession,
  getStoredAccessToken,
  getStoredRefreshToken,
  isAccessTokenExpiringSoon,
  isJwtAuthMode,
  storeAuthTokens,
} from '../auth/session'
import type {
  ApiResponse,
  AuthTokenPair,
  OAuthAuthorizeResult,
  AgentApprovalList,
  AgentFeedbackItem,
  AgentFeedbackList,
  AgentApprovalRequest,
  AgentAskResult,
  Nl2SqlQueryResult,
  AssistantResult,
  CurrentUser,
  DashboardOverview,
  HazardCreateResult,
  MetricCatalogPage,
  MetricDetail,
  ProfileData,
  ProjectListResponse,
  ProjectRankingItem,
  ProjectWeeklyReport,
  SubcontractorEvalReport,
  AttributionAnalysisResult,
  AttributionRequestPayload,
  BayesianConfigVersions,
  RuleTriggerLog,
  WorkOrder,
  WorkOrderCreatePayload,
  WorkOrderDetail,
  WorkOrderStatusPayload,
  WorkerListResponse,
} from '../types/api'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 12000,
})

let refreshPromise: Promise<string | null> | null = null

function setBearerToken(token: string | null) {
  if (token) {
    client.defaults.headers.common.Authorization = `Bearer ${token}`
  } else {
    delete client.defaults.headers.common.Authorization
  }
}

function clearMockAuthHeaders() {
  const mockHeaders = [
    'X-Mock-User-Id',
    'X-Mock-User-Name',
    'X-Role',
    'X-Tenant-Id',
    'X-Company-Id',
    'X-Org-Path',
    'X-Scope-Type',
    'X-Data-Scope',
    'X-Authorized-Project-Ids',
    'X-Subcontractor-Id',
  ]
  for (const header of mockHeaders) {
    delete client.defaults.headers.common[header]
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getStoredRefreshToken()
  if (!refreshToken) {
    return null
  }
  try {
    const response = await client.post<ApiResponse<AuthTokenPair>>('/auth/refresh', {
      refresh_token: refreshToken,
    })
    const data = response.data.data
    storeAuthTokens(data.access_token, data.refresh_token)
    setBearerToken(data.access_token)
    return data.access_token
  } catch {
    clearAuthSession()
    setBearerToken(null)
    return null
  }
}

client.interceptors.request.use((config) => {
  const accessToken = getStoredAccessToken()
  if (accessToken && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as (typeof error.config & { _retry?: boolean }) | undefined
    const status = error.response?.status
    const requestUrl = originalRequest?.url ?? ''

    if (
      status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !requestUrl.includes('/auth/login') &&
      !requestUrl.includes('/auth/refresh') &&
      getStoredRefreshToken()
    ) {
      originalRequest._retry = true
      refreshPromise ??= refreshAccessToken().finally(() => {
        refreshPromise = null
      })
      const nextToken = await refreshPromise
      if (nextToken) {
        originalRequest.headers.Authorization = `Bearer ${nextToken}`
        return client(originalRequest)
      }
    }

    if (status === 401 && isJwtAuthMode() && !requestUrl.includes('/auth/login')) {
      clearAuthSession()
      setBearerToken(null)
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.assign('/login')
      }
    }

    return Promise.reject(error)
  },
)

export interface MockAuthContext {
  userId: string
  userName: string
  role: string
  tenantId?: string
  companyId?: string
  orgPath?: string
  scopeType?: 'company' | 'project'
  dataScope?: 'tenant' | 'org'
  authorizedProjectIds?: string[]
  subcontractorId?: string | null
}

async function getData<T>(url: string): Promise<T> {
  const response = await client.get<ApiResponse<T>>(url)
  return response.data.data
}

async function postData<T>(url: string, body: unknown, timeoutMs?: number): Promise<T> {
  const response = await client.post<ApiResponse<T>>(url, body, timeoutMs ? { timeout: timeoutMs } : undefined)
  return response.data.data
}

async function postFormData<T>(url: string, body: FormData): Promise<T> {
  const response = await client.post<ApiResponse<T>>(url, body)
  return response.data.data
}

async function patchData<T>(url: string, body: unknown): Promise<T> {
  const response = await client.patch<ApiResponse<T>>(url, body)
  return response.data.data
}

async function patchFormData<T>(url: string, body: FormData): Promise<T> {
  const response = await client.patch<ApiResponse<T>>(url, body)
  return response.data.data
}

export const api = {
  health: () => getData<{ status: string }>('/health'),
  me: () => getData<CurrentUser>('/auth/me'),
  login: (body: { user_id: string; password: string; tenant_id?: string }) =>
    postData<AuthTokenPair>('/auth/login', body),
  refresh: (refreshToken: string) => postData<AuthTokenPair>('/auth/refresh', { refresh_token: refreshToken }),
  oauthAuthorize: () => getData<OAuthAuthorizeResult>('/auth/oauth/authorize'),
  oauthCallback: (params: { code: string; state?: string | null }) => {
    const search = new URLSearchParams({ code: params.code })
    if (params.state) search.set('state', params.state)
    return getData<AuthTokenPair>(`/auth/oauth/callback?${search.toString()}`)
  },
  refreshSessionIfNeeded: async (): Promise<boolean> => {
    if (!isJwtAuthMode()) return true
    const accessToken = getStoredAccessToken()
    const refreshToken = getStoredRefreshToken()
    if (!accessToken || !refreshToken) return false
    if (!isAccessTokenExpiringSoon(accessToken)) return true
    const nextToken = await refreshAccessToken()
    return Boolean(nextToken)
  },
  logout: () => {
    clearAuthSession()
    setBearerToken(null)
    clearMockAuthHeaders()
  },
  setBearerToken,
  clearMockAuthContext: clearMockAuthHeaders,
  setMockAuthContext: (context: MockAuthContext) => {
    client.defaults.headers.common['X-Mock-User-Id'] = context.userId
    client.defaults.headers.common['X-Mock-User-Name'] = context.userName
    client.defaults.headers.common['X-Role'] = context.role
    client.defaults.headers.common['X-Tenant-Id'] = context.tenantId ?? 'CSCEC'
    client.defaults.headers.common['X-Company-Id'] = context.companyId ?? context.tenantId ?? 'CSCEC'
    client.defaults.headers.common['X-Org-Path'] = context.orgPath ?? 'CSCEC'
    client.defaults.headers.common['X-Scope-Type'] = context.scopeType ?? 'project'
    client.defaults.headers.common['X-Data-Scope'] = context.dataScope ?? 'org'
    client.defaults.headers.common['X-Authorized-Project-Ids'] = (context.authorizedProjectIds ?? ['P002']).join(',')
    if (context.subcontractorId) {
      client.defaults.headers.common['X-Subcontractor-Id'] = context.subcontractorId
    } else {
      delete client.defaults.headers.common['X-Subcontractor-Id']
    }
  },
  dashboard: () => getData<DashboardOverview>('/dashboard/overview'),
  projects: () => getData<ProjectListResponse>('/projects'),
  projectRanking: () => getData<ProjectRankingItem[]>('/profile/ranking/projects'),
  projectProfile: (id: string) => getData<ProfileData>(`/profile/project/${id}`),
  workers: (params?: { project_id?: string; limit?: number }) => {
    const search = new URLSearchParams()
    if (params?.project_id) search.set('project_id', params.project_id)
    if (params?.limit) search.set('limit', String(params.limit))
    const suffix = search.toString() ? `?${search.toString()}` : ''
    return getData<WorkerListResponse>(`/profile/workers${suffix}`)
  },
  workerProfile: (id: string) => getData<ProfileData>(`/profile/worker/${id}`),
  subcontractorProfile: (id: string) => getData<ProfileData>(`/profile/subcontractor/${id}`),
  workOrders: (params?: { project_id?: string; status?: string }) =>
    getData<WorkOrder[]>(`/work-orders${params ? `?${new URLSearchParams(params as Record<string, string>)}` : ''}`),
  createProjectHazard: (projectId: string, body: FormData) =>
    postFormData<HazardCreateResult>(`/projects/${encodeURIComponent(projectId)}/hazards`, body),
  workOrderDetail: (workOrderId: string) => getData<WorkOrderDetail>(`/work-orders/${workOrderId}`),
  updateWorkOrderStatus: (workOrderId: string, payload: WorkOrderStatusPayload | string) =>
    patchData<{ work_order_id: string; new_status: string }>(
      `/work-orders/${workOrderId}/status`,
      typeof payload === 'string' ? { action: payload } : payload,
    ),
  submitRectification: (workOrderId: string, body: FormData) =>
    patchFormData<{ work_order_id: string; new_status: string }>(`/work-orders/${workOrderId}/status`, body),
  createWorkOrder: (body: WorkOrderCreatePayload) =>
    postData<{ work_order_id: string }>('/work-orders', body),
  fileUrl: (fileId: string) => `/api/v1/files/${encodeURIComponent(fileId)}`,
  metricsCatalog: (params?: { page_no?: number; page_size?: number; status?: string; keyword?: string }) => {
    const search = new URLSearchParams()
    if (params?.page_no) search.set('page_no', String(params.page_no))
    if (params?.page_size) search.set('page_size', String(params.page_size))
    if (params?.status) search.set('status', params.status)
    if (params?.keyword) search.set('keyword', params.keyword)
    const query = search.toString()
    return getData<MetricCatalogPage>(`/metrics/catalog${query ? `?${query}` : ''}`)
  },
  metricDetail: (metricCode: string) => getData<MetricDetail>(`/metrics/${encodeURIComponent(metricCode)}`),
  ruleTriggers: (params?: { project_id?: string; rule_id?: string }) => {
    const search = new URLSearchParams()
    if (params?.project_id) search.set('project_id', params.project_id)
    if (params?.rule_id) search.set('rule_id', params.rule_id)
    const query = search.toString()
    return getData<RuleTriggerLog[]>(`/rules/triggers${query ? `?${query}` : ''}`)
  },
  agentApprovals: (status?: string) =>
    getData<AgentApprovalList>(`/agent/approvals${status !== undefined ? `?status=${encodeURIComponent(status)}` : ''}`),
  agentApprovalDetail: (approvalId: string) =>
    getData<AgentApprovalRequest>(`/agent/approvals/${encodeURIComponent(approvalId)}`),
  approveAgentRequest: (approvalId: string, comment?: string | null) =>
    postData<AgentApprovalRequest>(`/agent/approvals/${encodeURIComponent(approvalId)}/approve`, { comment: comment ?? null }),
  rejectAgentRequest: (approvalId: string, comment?: string | null) =>
    postData<AgentApprovalRequest>(`/agent/approvals/${encodeURIComponent(approvalId)}/reject`, { comment: comment ?? null }),
  executeAgentApproval: (approvalId: string) =>
    postData<AgentApprovalRequest>(`/agent/approvals/${encodeURIComponent(approvalId)}/execute`, {}),
  submitAgentFeedback: (body: {
    task_id: string
    agent_name: string
    feedback_type: 'thumb' | 'rating' | 'correction' | 'adoption'
    rating?: number
    feedback_reason?: string
    original_output?: Record<string, unknown>
    corrected_output?: Record<string, unknown>
    correction_text?: string
    related_work_order_id?: string
    project_id?: string
  }) => postData<AgentFeedbackItem>('/agent/feedback', body),
  listAgentFeedback: (params?: {
    agent_name?: string
    feedback_type?: string
    task_id?: string
    label_status?: string
    limit?: number
  }) => {
    const search = new URLSearchParams()
    if (params?.agent_name) search.set('agent_name', params.agent_name)
    if (params?.feedback_type) search.set('feedback_type', params.feedback_type)
    if (params?.task_id) search.set('task_id', params.task_id)
    if (params?.label_status) search.set('label_status', params.label_status)
    if (params?.limit) search.set('limit', String(params.limit))
    const query = search.toString()
    return getData<AgentFeedbackList>(`/agent/feedback${query ? `?${query}` : ''}`)
  },
  agentAsk: (
    message: string,
    options?: {
      context?: Record<string, unknown>
      execution_mode?: string
      session_id?: string
      timeoutMs?: number
    },
  ) =>
    postData<AgentAskResult>(
      '/agent/ask',
      {
        message,
        context: options?.context ?? null,
        execution_mode: options?.execution_mode ?? 'route_only',
        session_id: options?.session_id ?? null,
      },
      options?.timeoutMs ?? 45000,
    ),
  nl2sqlQuery: (body: {
    question?: string
    execute?: boolean
    provider?: 'mock' | 'qwen' | 'disabled'
    mock_llm_output?: string
    clarification_id?: string
    clarification_reply?: string
    session_id?: string
  }) => postData<Nl2SqlQueryResult>('/agent/nl2sql', body),
  assistantChat: (message: string, context?: Record<string, unknown>) =>
    postData<AssistantResult>('/assistant/chat', { message, context }),
  projectRiskExplanation: (projectId: string) =>
    postData<AssistantResult>('/assistant/project-risk-explanation', { project_id: projectId }),
  projectWeeklyReport: (projectId: string, weekEnd?: string) => {
    const query = weekEnd ? `?week_end=${encodeURIComponent(weekEnd)}` : ''
    return getData<ProjectWeeklyReport>(`/reports/project-weekly/${encodeURIComponent(projectId)}${query}`)
  },
  subcontractorEvalReport: (
    subcontractorId: string,
    params?: { project_id?: string; eval_date?: string },
  ) => {
    const search = new URLSearchParams()
    if (params?.project_id) search.set('project_id', params.project_id)
    if (params?.eval_date) search.set('eval_date', params.eval_date)
    const query = search.toString()
    return getData<SubcontractorEvalReport>(
      `/reports/subcontractor-eval/${encodeURIComponent(subcontractorId)}${query ? `?${query}` : ''}`,
    )
  },
  attributionAnalysis: (body: AttributionRequestPayload) =>
    postData<AttributionAnalysisResult>('/analysis/attribution', body),
  bayesianVersions: () => getData<BayesianConfigVersions>('/config/bayesian-versions'),
}
