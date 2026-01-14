import type { QCReport as QCReportType } from '../types';

interface QCReportProps {
  report: QCReportType;
}

export function QCReport({ report }: QCReportProps) {
  const { summary, issues } = report;

  return (
    <div className="qc-report">
      <div className={`qc-summary ${summary.passed ? 'passed' : 'failed'}`}>
        <div className="summary-header">
          <span className="status-icon">{summary.passed ? '✓' : '✗'}</span>
          <span className="status-text">
            {summary.passed ? 'QC Passed' : 'QC Failed'}
          </span>
        </div>
        
        <div className="summary-stats">
          <div className="stat">
            <span className="stat-value">{summary.total_cues}</span>
            <span className="stat-label">Total Cues</span>
          </div>
          <div className="stat errors">
            <span className="stat-value">{summary.errors_count}</span>
            <span className="stat-label">Errors</span>
          </div>
          <div className="stat warnings">
            <span className="stat-value">{summary.warnings_count}</span>
            <span className="stat-label">Warnings</span>
          </div>
        </div>
      </div>

      {Object.keys(summary.by_type).length > 0 && (
        <div className="issues-by-type">
          <h4>Issues by Type</h4>
          <ul>
            {Object.entries(summary.by_type).map(([type, count]) => (
              <li key={type}>
                <span className="issue-type">{type.replace(/_/g, ' ')}</span>
                <span className="issue-count">{count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {issues.length > 0 && (
        <div className="issues-list">
          <h4>Issues ({issues.length})</h4>
          <div className="issues-scroll">
            {issues.slice(0, 50).map((issue, i) => (
              <div
                key={i}
                className={`issue-item ${issue.severity}`}
              >
                <span className="issue-cue">Cue {issue.cue_index}</span>
                <span className="issue-message">{issue.message}</span>
              </div>
            ))}
            {issues.length > 50 && (
              <p className="issues-more">
                ... and {issues.length - 50} more issues. Download the full report.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
