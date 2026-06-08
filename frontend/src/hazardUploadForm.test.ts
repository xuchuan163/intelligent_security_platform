import { buildHazardUploadFormData, validateHazardUploadDraft } from './hazardUploadForm'

function assertEqual<T>(actual: T, expected: T, message: string) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${String(expected)}, got ${String(actual)}`)
  }
}

const image = new Blob(['demo-image'], { type: 'image/jpeg' })
const draft = {
  projectId: 'P002',
  description: '临边防护栏杆缺失，存在高处坠落风险',
  hazardType: 'edge_protection',
  hazardLevel: 'general' as const,
  subcontractorId: 'S003',
  dueDate: '2026-06-09',
  location: '2号楼3层西侧',
  images: [image],
}

assertEqual(validateHazardUploadDraft(draft), null, 'valid draft has no validation error')

const formData = buildHazardUploadFormData(draft)
assertEqual(formData.get('description'), draft.description, 'description field')
assertEqual(formData.get('hazard_type'), draft.hazardType, 'hazard type field')
assertEqual(formData.get('hazard_level'), draft.hazardLevel, 'hazard level field')
assertEqual(formData.get('subcontractor_id'), draft.subcontractorId, 'subcontractor field')
assertEqual(formData.get('due_date'), draft.dueDate, 'due date field')
assertEqual(formData.get('location'), draft.location, 'location field')
assertEqual(formData.getAll('images').length, 1, 'images field count')

assertEqual(
  validateHazardUploadDraft({ ...draft, images: [] }),
  '请至少上传一张隐患图片。',
  'image is required',
)
assertEqual(
  validateHazardUploadDraft({ ...draft, description: '太短' }),
  '隐患描述至少需要 10 个字。',
  'description length is validated',
)
