import { apiClient } from './client';

export interface ImportJob {
  id: number;
  group: number;
  uploaded_by: number;
  original_filename: string;
  status: 'pending' | 'processing' | 'review_required' | 'completed' | 'failed';
  created_at: string;
  completed_at: string | null;
  row_count: number;
}

export interface ImportAnomaly {
  id: number;
  import_job: number;
  import_row: number;
  anomaly_type: string;
  anomaly_category: 'duplicate' | 'membership' | 'currency' | 'date' | 'settlement' | 'split' | 'validation' | 'unknown_user';
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  detected_action: string;
  user_decision: 'approve' | 'reject' | 'ignore' | null;
  created_at: string;
}

export interface ImportDecision {
  id: number;
  anomaly: number;
  decision: 'approve' | 'reject' | 'ignore';
  decided_by: number;
  decision_reason: string;
  created_at: string;
}

export interface ImportReport {
  id: number;
  import_job: number;
  total_rows: number;
  imported_rows: number;
  skipped_rows: number;
  failed_rows: number;
  anomaly_count: number;
  report_json: {
    total_rows: number;
    imported_rows: number;
    skipped_rows: number;
    failed_rows: number;
    review_required_rows: number;
    anomaly_count: number;
    anomaly_breakdown: Record<string, number>;
    anomalies: any[];
  };
}

export async function listImportJobs(): Promise<ImportJob[]> {
  const response = await apiClient.get('/api/imports/');
  return response.data;
}

export async function getImportJob(id: number): Promise<ImportJob> {
  const response = await apiClient.get(`/api/imports/${id}/`);
  return response.data;
}

export async function uploadCSV(groupId: number, file: File): Promise<ImportJob> {
  const formData = new FormData();
  formData.append('group_id', groupId.toString());
  formData.append('file', file);
  
  const response = await apiClient.post('/api/imports/upload/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
}

export async function listJobAnomalies(jobId: number): Promise<ImportAnomaly[]> {
  const response = await apiClient.get(`/api/imports/${jobId}/anomalies/`);
  return response.data;
}

export async function submitAnomalyDecision(
  anomalyId: number,
  decision: 'approve' | 'reject' | 'ignore',
  reason: string
): Promise<ImportDecision> {
  const response = await apiClient.post(`/api/imports/anomalies/${anomalyId}/decision/`, {
    decision,
    decision_reason: reason,
  });
  return response.data;
}

export async function getImportReport(jobId: number): Promise<ImportReport> {
  const response = await apiClient.get(`/api/imports/${jobId}/report/`);
  return response.data;
}
