import { useState, useEffect, useCallback } from 'react';
import type { QCIssue, FixOption, FixSuggestions, MetricsResult } from '../types';
import { getFixSuggestions, applyFix, calculateMetrics } from '../api/client';

interface IssueResolverProps {
  jobId: string;
  issue: QCIssue;
  onFixApplied: () => void;
  onClose: () => void;
}

export function IssueResolver({ jobId, issue, onFixApplied, onClose }: IssueResolverProps) {
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [suggestions, setSuggestions] = useState<FixSuggestions | null>(null);
  const [selectedOption, setSelectedOption] = useState<number | 'manual'>(-1);
  const [manualText, setManualText] = useState('');
  const [metrics, setMetrics] = useState<MetricsResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch suggestions on mount
  useEffect(() => {
    async function fetchSuggestions() {
      try {
        setLoading(true);
        setError(null);
        const data = await getFixSuggestions(jobId, issue.cue_index);
        setSuggestions(data);
        setManualText(data.original_text);
        
        // Auto-select first applicable option
        const firstApplicable = data.options.findIndex(opt => opt.is_applicable);
        if (firstApplicable >= 0) {
          setSelectedOption(firstApplicable);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load suggestions');
      } finally {
        setLoading(false);
      }
    }
    fetchSuggestions();
  }, [jobId, issue.cue_index]);

  // Calculate metrics when manual text changes
  const updateMetrics = useCallback(async (text: string) => {
    try {
      const result = await calculateMetrics(jobId, issue.cue_index, text);
      setMetrics(result);
    } catch (err) {
      console.error('Failed to calculate metrics:', err);
    }
  }, [jobId, issue.cue_index]);

  // Debounced metrics calculation
  useEffect(() => {
    if (selectedOption === 'manual' && manualText) {
      const timer = setTimeout(() => updateMetrics(manualText), 300);
      return () => clearTimeout(timer);
    }
  }, [manualText, selectedOption, updateMetrics]);

  const handleApply = async () => {
    if (!suggestions) return;

    try {
      setApplying(true);
      setError(null);

      let fixType: string;
      let newText: string | undefined;
      let newStartMs: number | undefined;
      let newEndMs: number | undefined;

      if (selectedOption === 'manual') {
        fixType = 'manual';
        newText = manualText;
      } else if (selectedOption >= 0 && selectedOption < suggestions.options.length) {
        const option = suggestions.options[selectedOption];
        fixType = option.fix_type;
        newText = option.preview_text;
        newStartMs = option.new_start_ms;
        newEndMs = option.new_end_ms;
      } else {
        setError('Please select a fix option');
        return;
      }

      await applyFix(jobId, issue.cue_index, fixType, newText, newStartMs, newEndMs);
      onFixApplied();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply fix');
    } finally {
      setApplying(false);
    }
  };

  const getFixTypeIcon = (fixType: string) => {
    switch (fixType) {
      case 'compress': return '📝';
      case 'extend_timing': return '⏱️';
      case 'split_cue': return '✂️';
      case 'reflow': return '↩️';
      default: return '🔧';
    }
  };

  const getConfidenceClass = (confidence: number) => {
    if (confidence >= 0.8) return 'confidence-high';
    if (confidence >= 0.5) return 'confidence-medium';
    return 'confidence-low';
  };

  if (loading) {
    return (
      <div className="issue-resolver">
        <div className="resolver-loading">
          <div className="spinner"></div>
          <p>Generating fix suggestions...</p>
        </div>
      </div>
    );
  }

  if (error && !suggestions) {
    return (
      <div className="issue-resolver">
        <div className="resolver-error">
          <p>❌ {error}</p>
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    );
  }

  return (
    <div className="issue-resolver">
      <div className="resolver-header">
        <h3>Fix Cue #{issue.cue_index}</h3>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>

      <div className="resolver-issue">
        <span className={`severity ${issue.severity}`}>{issue.severity.toUpperCase()}</span>
        <span className="message">{issue.message}</span>
      </div>

      {suggestions && (
        <>
          <div className="current-metrics">
            <h4>Current Status</h4>
            <div className="metrics-grid">
              <div className={`metric ${suggestions.current_cps > suggestions.constraints.max_cps ? 'violation' : ''}`}>
                <span className="value">{suggestions.current_cps}</span>
                <span className="label">CPS (max: {suggestions.constraints.max_cps})</span>
              </div>
              <div className={`metric ${suggestions.current_max_line_length > suggestions.constraints.max_chars_per_line ? 'violation' : ''}`}>
                <span className="value">{suggestions.current_max_line_length}</span>
                <span className="label">Max Line (max: {suggestions.constraints.max_chars_per_line})</span>
              </div>
              <div className={`metric ${suggestions.current_line_count > suggestions.constraints.max_lines ? 'violation' : ''}`}>
                <span className="value">{suggestions.current_line_count}</span>
                <span className="label">Lines (max: {suggestions.constraints.max_lines})</span>
              </div>
            </div>
          </div>

          <div className="fix-options">
            <h4>Suggested Fixes</h4>
            
            {suggestions.options.map((option, idx) => (
              <label
                key={idx}
                className={`fix-option ${!option.is_applicable ? 'disabled' : ''} ${selectedOption === idx ? 'selected' : ''}`}
              >
                <input
                  type="radio"
                  name="fix-option"
                  checked={selectedOption === idx}
                  onChange={() => setSelectedOption(idx)}
                  disabled={!option.is_applicable}
                />
                <div className="option-content">
                  <div className="option-header">
                    <span className="icon">{getFixTypeIcon(option.fix_type)}</span>
                    <span className="description">{option.description}</span>
                    {option.is_applicable && (
                      <span className={`confidence ${getConfidenceClass(option.confidence)}`}>
                        {Math.round(option.confidence * 100)}%
                      </span>
                    )}
                  </div>
                  
                  {option.is_applicable ? (
                    <div className="option-preview">
                      <pre dir="auto">{option.preview_text}</pre>
                      {option.resulting_cps && (
                        <span className={`result-metric ${option.resulting_cps <= suggestions.constraints.max_cps ? 'valid' : 'invalid'}`}>
                          CPS: {option.resulting_cps}
                        </span>
                      )}
                    </div>
                  ) : (
                    <div className="option-reason">
                      {option.reason}
                    </div>
                  )}
                </div>
              </label>
            ))}

            {/* Manual edit option */}
            <label className={`fix-option ${selectedOption === 'manual' ? 'selected' : ''}`}>
              <input
                type="radio"
                name="fix-option"
                checked={selectedOption === 'manual'}
                onChange={() => setSelectedOption('manual')}
              />
              <div className="option-content">
                <div className="option-header">
                  <span className="icon">✏️</span>
                  <span className="description">Manual Edit</span>
                </div>
              </div>
            </label>

            {selectedOption === 'manual' && (
              <div className="manual-editor">
                <textarea
                  value={manualText}
                  onChange={(e) => setManualText(e.target.value)}
                  rows={4}
                  dir="auto"
                  placeholder="Enter your custom text..."
                />
                
                {metrics && (
                  <div className="live-metrics">
                    <div className={`metric ${!metrics.is_valid ? 'violation' : 'valid'}`}>
                      <span>CPS: {metrics.metrics.cps}</span>
                      <span>Line: {metrics.metrics.max_line_length}</span>
                      <span>Lines: {metrics.metrics.line_count}</span>
                      <span>Chars: {metrics.metrics.char_count}</span>
                    </div>
                    {metrics.violations.length > 0 && (
                      <ul className="violations-list">
                        {metrics.violations.map((v, i) => (
                          <li key={i}>⚠️ {v}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {error && (
        <div className="resolver-error-inline">
          ❌ {error}
        </div>
      )}

      <div className="resolver-actions">
        <button className="btn-secondary" onClick={onClose} disabled={applying}>
          Cancel
        </button>
        <button
          className="btn-primary"
          onClick={handleApply}
          disabled={applying || selectedOption === -1}
        >
          {applying ? 'Applying...' : 'Apply Fix'}
        </button>
      </div>
    </div>
  );
}

// Batch auto-fix component
interface BatchAutoFixProps {
  jobId: string;
  issueType?: string;
  issueCount: number;
  onComplete: () => void;
}

export function BatchAutoFix({ jobId, issueType, issueCount, onComplete }: BatchAutoFixProps) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<{
    fixed: number;
    failed: number;
    remaining: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAutoFix = async () => {
    try {
      setRunning(true);
      setError(null);
      
      const { autoFixAll } = await import('../api/client');
      const response = await autoFixAll(jobId, issueType, 50);
      
      setResult({
        fixed: response.fixed_count,
        failed: response.failed_count,
        remaining: response.remaining_issues,
      });
      
      if (response.fixed_count > 0) {
        onComplete();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Auto-fix failed');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="batch-auto-fix">
      <button
        className="btn-auto-fix"
        onClick={handleAutoFix}
        disabled={running || issueCount === 0}
      >
        {running ? (
          <>
            <span className="spinner-small"></span>
            Fixing...
          </>
        ) : (
          <>
            🔧 Auto-fix {issueType ? issueType.replace(/_/g, ' ') : 'all'} ({issueCount})
          </>
        )}
      </button>
      
      {result && (
        <div className="auto-fix-result">
          ✅ Fixed: {result.fixed} | ❌ Failed: {result.failed} | Remaining: {result.remaining}
        </div>
      )}
      
      {error && (
        <div className="auto-fix-error">
          ❌ {error}
        </div>
      )}
    </div>
  );
}
