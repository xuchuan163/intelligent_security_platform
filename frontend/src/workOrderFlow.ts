export type WorkOrderStatus =
  | 'pending_confirm'
  | 'dispatched'
  | 'processing'
  | 'waiting_review'
  | 'closed'
  | 'rejected'
  | 'overdue_escalated'

export type WorkOrderAction = 'confirm' | 'accept' | 'submit_result' | 'review_pass' | 'review_reject'

export type WorkOrderRole = 'gc_safety_officer' | 'safety_director' | 'sub_safety_officer' | string

export interface WorkOrderActionItem {
  action: WorkOrderAction
  label: string
  tone: 'primary' | 'success' | 'warning' | 'danger'
  nextStatus: WorkOrderStatus
  role: WorkOrderRole
}

const STATUS_LABELS: Record<WorkOrderStatus, string> = {
  pending_confirm: '待确认',
  dispatched: '已派发',
  processing: '整改中',
  waiting_review: '待验收',
  closed: '已闭环',
  rejected: '已驳回',
  overdue_escalated: '超期升级',
}

const ACTIONS_BY_STATUS: Partial<Record<WorkOrderStatus, WorkOrderActionItem[]>> = {
  pending_confirm: [
    {
      action: 'confirm',
      label: '审批派发',
      tone: 'primary',
      nextStatus: 'dispatched',
      role: 'safety_director',
    },
  ],
  dispatched: [
    {
      action: 'accept',
      label: '接单整改',
      tone: 'primary',
      nextStatus: 'processing',
      role: 'sub_safety_officer',
    },
  ],
  processing: [
    {
      action: 'submit_result',
      label: '提交整改',
      tone: 'warning',
      nextStatus: 'waiting_review',
      role: 'sub_safety_officer',
    },
  ],
  waiting_review: [
    {
      action: 'review_pass',
      label: '验收通过',
      tone: 'success',
      nextStatus: 'closed',
      role: 'gc_safety_officer',
    },
    {
      action: 'review_reject',
      label: '驳回整改',
      tone: 'danger',
      nextStatus: 'processing',
      role: 'gc_safety_officer',
    },
  ],
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status as WorkOrderStatus] ?? status
}

export function availableWorkOrderActions(status: string, role?: WorkOrderRole): WorkOrderActionItem[] {
  const actions = ACTIONS_BY_STATUS[status as WorkOrderStatus] ?? []
  if (!role) {
    return actions
  }
  return actions.filter((item) => item.role === role)
}

export function canPerformWorkOrderAction(status: string, action: string, role?: WorkOrderRole): boolean {
  return availableWorkOrderActions(status, role).some((item) => item.action === action)
}

export function nextStatusForAction(status: string, action: string): WorkOrderStatus | null {
  return availableWorkOrderActions(status).find((item) => item.action === action)?.nextStatus ?? null
}

export function actionRequiresDetail(action: WorkOrderAction): boolean {
  return action === 'confirm' || action === 'submit_result' || action === 'review_reject'
}
