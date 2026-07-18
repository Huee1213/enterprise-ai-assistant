import apiClient from './client'
import type { DocumentInfo, UploadResponse } from '@/types'

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.post<UploadResponse>('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return data
}

export async function uploadDocumentsBulk(files: File[]): Promise<{ total: number; success: number; failed: number; results: UploadResponse[] }> {
  const formData = new FormData()
  for (const f of files) {
    formData.append('files', f)
  }
  const { data } = await apiClient.post('/documents/upload-bulk', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
  })
  return data
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  const { data } = await apiClient.get<DocumentInfo[]>('/documents/list')
  return data
}

export async function deleteDocument(id: string): Promise<void> {
  await apiClient.delete(`/documents/${id}`)
}
