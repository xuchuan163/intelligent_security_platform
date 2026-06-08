export type HazardLevel = 'general' | 'major'

export interface HazardUploadDraft {
  projectId: string
  description: string
  hazardType: string
  hazardLevel: HazardLevel
  subcontractorId: string
  dueDate: string
  location?: string | null
  images: Array<Blob & { name?: string }>
}

export function validateHazardUploadDraft(draft: HazardUploadDraft): string | null {
  if (!draft.projectId.trim()) {
    return '请选择项目。'
  }
  if (draft.description.trim().length < 10) {
    return '隐患描述至少需要 10 个字。'
  }
  if (!draft.hazardType.trim()) {
    return '请选择隐患类型。'
  }
  if (!draft.subcontractorId.trim()) {
    return '请填写责任分包。'
  }
  if (!draft.dueDate) {
    return '请选择整改期限。'
  }
  if (draft.images.length === 0) {
    return '请至少上传一张隐患图片。'
  }
  return null
}

export function buildHazardUploadFormData(draft: HazardUploadDraft): FormData {
  const formData = new FormData()
  formData.append('description', draft.description.trim())
  formData.append('hazard_type', draft.hazardType.trim())
  formData.append('hazard_level', draft.hazardLevel)
  formData.append('subcontractor_id', draft.subcontractorId.trim())
  formData.append('due_date', draft.dueDate)
  if (draft.location?.trim()) {
    formData.append('location', draft.location.trim())
  }
  draft.images.forEach((image, index) => {
    formData.append('images', image, image.name || `hazard-${index + 1}.jpg`)
  })
  return formData
}
