export type AgentApprovalStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'executed'
  | 'execution_failed'
  | 'expired'

const STATUS_LABELS: Record<AgentApprovalStatus, string> = {
  pending: '待审批',
  approved: '已批准',
  rejected: '已驳回',
  executed: '已执行',
  execution_failed: '执行失败',
  expired: '已过期',
}

const STATUS_CLASS: Record<AgentApprovalStatus, string> = {
  pending: 'status-pending_confirm',
  approved: 'status-dispatched',
  rejected: 'status-overdue_escalated',
  executed: 'status-closed',
  execution_failed: 'status-waiting_review',
  expired: 'status-closed',
}

export function approvalStatusLabel(status: string): string {
  return STATUS_LABELS[status as AgentApprovalStatus] ?? status
}

export function approvalStatusClass(status: string): string {
  return STATUS_CLASS[status as AgentApprovalStatus] ?? 'status-dispatched'
}

export function canApprove(status: string): boolean {
  return status === 'pending'
}

export function canExecute(status: string, tool: string): boolean {
  return status === 'approved' && (tool === 'work_orders.transition' || tool === 'work_orders.create')
}
