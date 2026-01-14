export interface SubtitleSegment {
  index: number;
  start_ms: number;
  end_ms: number;
  text: string;
  translated_text: string | null;
  qc_flags: string[];
}

export interface JobConstraints {
  max_lines: number;
  max_chars_per_line: number;
  max_cps: number;
  min_duration_ms: number;
}

export interface QCIssue {
  cue_index: number;
  issue_type: string;
  severity: 'error' | 'warning';
  message: string;
  value?: number;
  threshold?: number;
}

export interface QCSummary {
  total_cues: number;
  issues_count: number;
  errors_count: number;
  warnings_count: number;
  passed: boolean;
  by_type: Record<string, number>;
}

export interface QCReport {
  issues: QCIssue[];
  summary: QCSummary;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  error?: string;
  qc_summary?: QCSummary;
}

export interface JobResult {
  job_id: string;
  segments: SubtitleSegment[];
  qc_report: QCReport;
}

export interface JobConfig {
  source_lang: string;
  target_lang: string;
  constraints: JobConstraints;
  glossary: Record<string, string>;
  dry_run: boolean;
}
