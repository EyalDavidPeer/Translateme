export type GenderForm = 'masculine' | 'feminine' | 'neutral' | 'unknown';

export interface GenderAlternative {
  gender: GenderForm;
  text: string;
  confidence: number;
}

export interface SubtitleSegment {
  index: number;
  start_ms: number;
  end_ms: number;
  text: string;
  translated_text: string | null;
  qc_flags: string[];
  // Gender-related fields
  gender_alternatives?: GenderAlternative[];
  active_gender?: GenderForm;
  gender_confidence?: number;
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

// Fix suggestion types
export interface FixOption {
  fix_type: 'compress' | 'extend_timing' | 'split_cue' | 'reflow' | 'manual';
  description: string;
  preview_text: string;
  new_start_ms?: number;
  new_end_ms?: number;
  resulting_cps?: number;
  resulting_line_length?: number;
  confidence: number;
  is_applicable: boolean;
  reason?: string;
}

export interface FixSuggestions {
  cue_index: number;
  original_text: string;
  current_cps: number;
  current_max_line_length: number;
  current_line_count: number;
  issues: string[];
  options: FixOption[];
  constraints: {
    max_cps: number;
    max_chars_per_line: number;
    max_lines: number;
    min_duration_ms: number;
  };
}

export interface MetricsResult {
  cue_index: number;
  text: string;
  metrics: {
    cps: number;
    max_line_length: number;
    line_count: number;
    char_count: number;
    duration_ms: number;
  };
  constraints: {
    max_cps: number;
    max_chars_per_line: number;
    max_lines: number;
  };
  is_valid: boolean;
  violations: string[];
}

export interface AutoFixResult {
  status: string;
  fixed_count: number;
  failed_count: number;
  fixed_cues: Array<{
    cue_index: number;
    fix_type: string;
    description: string;
  }>;
  remaining_issues: number;
  qc_summary: QCSummary;
}

// Gender API types
export interface GenderAlternativesResponse {
  cue_index: number;
  current_text: string;
  active_gender: GenderForm;
  confidence: number;
  alternatives: GenderAlternative[];
  has_alternatives: boolean;
}

export interface SetGenderResponse {
  status: string;
  cue_index: number;
  new_gender: GenderForm;
  new_text: string;
  qc_summary: QCSummary;
}

export interface BatchSetGenderResponse {
  status: string;
  updated_count: number;
  gender: GenderForm;
  qc_summary: QCSummary;
}
