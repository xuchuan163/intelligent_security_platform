import {
  actionRequiresDetail,
  availableWorkOrderActions,
  canPerformWorkOrderAction,
  nextStatusForAction,
  statusLabel,
} from './workOrderFlow'

function assertEqual<T>(actual: T, expected: T, message: string) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${String(expected)}, got ${String(actual)}`)
  }
}

const pendingActions = availableWorkOrderActions('pending_confirm')
assertEqual(pendingActions.length, 1, 'pending_confirm action count')
assertEqual(pendingActions[0].action, 'confirm', 'pending_confirm first action')
assertEqual(nextStatusForAction('pending_confirm', 'confirm'), 'dispatched', 'confirm next status')

const directorActions = availableWorkOrderActions('pending_confirm', 'safety_director')
assertEqual(directorActions.length, 1, 'safety director can confirm pending work orders')
assertEqual(canPerformWorkOrderAction('pending_confirm', 'confirm', 'safety_director'), true, 'director confirm permission')
assertEqual(canPerformWorkOrderAction('pending_confirm', 'confirm', 'gc_safety_officer'), false, 'gc officer cannot confirm')

const subcontractorActions = availableWorkOrderActions('processing', 'sub_safety_officer')
assertEqual(subcontractorActions.length, 1, 'subcontractor officer can submit rectification')
assertEqual(subcontractorActions[0].action, 'submit_result', 'processing action')
assertEqual(actionRequiresDetail('confirm'), true, 'confirm needs assignee and due time')
assertEqual(actionRequiresDetail('submit_result'), true, 'submit result needs image and comment')
assertEqual(actionRequiresDetail('accept'), false, 'accept does not need extra fields')

const reviewActions = availableWorkOrderActions('waiting_review', 'gc_safety_officer')
assertEqual(reviewActions.length, 2, 'gc officer can review waiting work orders')
assertEqual(reviewActions[0].action, 'review_pass', 'waiting_review first action')
assertEqual(reviewActions[1].action, 'review_reject', 'waiting_review second action')
assertEqual(statusLabel('closed'), '已闭环', 'closed label')
