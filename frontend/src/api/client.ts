import axios from 'axios'

import type {
  ApiResponse,
  AssistantResult,
  DashboardOverview,
  ProfileData,
  ProjectRankingItem,
  WorkOrder,
} from '../types/api'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 12000,
})

async function getData<T>(url: string): Promise<T> {
  const response = await client.get<ApiResponse<T>>(url)
  return response.data.data
}

async function postData<T>(url: string, body: unknown): Promise<T> {
  const response = await client.post<ApiResponse<T>>(url, body)
  return response.data.data
}

async function patchData<T>(url: string, body: unknown): Promise<T> {
  const response = await client.patch<ApiResponse<T>>(url, body)
  return response.data.data
}

export const api = {
  dashboard: () => getData<DashboardOverview>('/dashboard/overview'),
  projectRanking: () => getData<ProjectRankingItem[]>('/profile/ranking/projects'),
  projectProfile: (id: string) => getData<ProfileData>(`/profile/project/${id}`),
  workerProfile: (id: string) => getData<ProfileData>(`/profile/worker/${id}`),
  subcontractorProfile: (id: string) => getData<ProfileData>(`/profile/subcontractor/${id}`),
  workOrders: (params?: { project_id?: string; status?: string }) =>
    getData<WorkOrder[]>(`/work-orders${params ? `?${new URLSearchParams(params as Record<string, string>)}` : ''}`),
  updateWorkOrderStatus: (workOrderId: string, action: string) =>
    patchData<{ work_order_id: string; new_status: string }>(`/work-orders/${workOrderId}/status`, { action }),
  ruleTriggers: () => getData<Array<Record<string, unknown>>>('/work-orders/triggers'),
  assistantChat: (message: string, context?: Record<string, unknown>) =>
    postData<AssistantResult>('/assistant/chat', { message, context }),
  projectRiskExplanation: (projectId: string) =>
    postData<AssistantResult>('/assistant/project-risk-explanation', { project_id: projectId }),
}
