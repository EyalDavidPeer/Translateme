import type { 
  JobStatus, 
  JobResult, 
  JobConfig, 
  FixSuggestions, 
  MetricsResult, 
  AutoFixResult, 
  QCSummary,
  GenderAlternativesResponse,
  SetGenderResponse,
  BatchSetGenderResponse,
  GenderForm
} from '../types';

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

// Fix suggestion APIs
export async function getFixSuggestions(jobId: string, cueIndex: number): Promise<FixSuggestions> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/suggest-fixes/${cueIndex}`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get fix suggestions');
  }

  return response.json();
}

export async function applyFix(
  jobId: string,
  cueIndex: number,
  fixType: string,
  newText?: string,
  newStartMs?: number,
  newEndMs?: number
): Promise<{
  status: string;
  cue_index: number;
  fix_applied: string;
  new_text: string;
  new_cps: number;
  new_max_line_length: number;
  qc_summary: QCSummary;
}> {
  const formData = new FormData();
  formData.append('fix_type', fixType);
  if (newText !== undefined) formData.append('new_text', newText);
  if (newStartMs !== undefined) formData.append('new_start_ms', newStartMs.toString());
  if (newEndMs !== undefined) formData.append('new_end_ms', newEndMs.toString());

  const response = await fetch(`${API_BASE}/jobs/${jobId}/segments/${cueIndex}`, {
    method: 'PATCH',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to apply fix');
  }

  return response.json();
}

export async function autoFixAll(
  jobId: string,
  issueType?: string,
  maxFixes: number = 50
): Promise<AutoFixResult> {
  const formData = new FormData();
  if (issueType) formData.append('issue_type', issueType);
  formData.append('max_fixes', maxFixes.toString());

  const response = await fetch(`${API_BASE}/jobs/${jobId}/auto-fix`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to auto-fix');
  }

  return response.json();
}

export async function calculateMetrics(
  jobId: string,
  cueIndex: number,
  text: string
): Promise<MetricsResult> {
  const params = new URLSearchParams({
    cue_index: cueIndex.toString(),
    text: text,
  });

  const response = await fetch(`${API_BASE}/jobs/${jobId}/calculate-metrics?${params}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to calculate metrics');
  }

  return response.json();
}

// Gender API functions
export async function getGenderAlternatives(
  jobId: string,
  cueIndex: number
): Promise<GenderAlternativesResponse> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/segments/${cueIndex}/gender-alternatives`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get gender alternatives');
  }

  return response.json();
}

export async function setSegmentGender(
  jobId: string,
  cueIndex: number,
  gender: GenderForm
): Promise<SetGenderResponse> {
  const formData = new FormData();
  formData.append('gender', gender);

  const response = await fetch(`${API_BASE}/jobs/${jobId}/segments/${cueIndex}/gender`, {
    method: 'PATCH',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to set gender');
  }

  return response.json();
}

export async function batchSetGender(
  jobId: string,
  gender: GenderForm,
  cueIndices?: number[]
): Promise<BatchSetGenderResponse> {
  const formData = new FormData();
  formData.append('gender', gender);
  if (cueIndices) {
    formData.append('cue_indices', cueIndices.join(','));
  }

  const response = await fetch(`${API_BASE}/jobs/${jobId}/batch-set-gender`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to batch set gender');
  }

  return response.json();
}
