import type { JobStatus, JobResult, JobConfig } from '../types';

const API_BASE = '/api';

export async function createJob(
  file: File,
  config: JobConfig
): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('source_lang', config.source_lang);
  formData.append('target_lang', config.target_lang);
  formData.append('max_lines', config.constraints.max_lines.toString());
  formData.append('max_chars_per_line', config.constraints.max_chars_per_line.toString());
  formData.append('max_cps', config.constraints.max_cps.toString());
  formData.append('min_duration_ms', config.constraints.min_duration_ms.toString());
  formData.append('dry_run', config.dry_run.toString());
  
  if (Object.keys(config.glossary).length > 0) {
    formData.append('glossary', JSON.stringify(config.glossary));
  }

  const response = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create job');
  }

  return response.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}`);
  
  if (!response.ok) {
    throw new Error('Failed to get job status');
  }

  return response.json();
}

export async function getJobResult(jobId: string): Promise<JobResult> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/result`);
  
  if (!response.ok) {
    throw new Error('Failed to get job result');
  }

  return response.json();
}

export function getDownloadUrl(jobId: string, format: 'srt' | 'vtt'): string {
  return `${API_BASE}/jobs/${jobId}/download/${format}`;
}

export function getQCReportUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/qc-report`;
}
