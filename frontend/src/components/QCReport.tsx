import { useState } from 'react';
import type { QCReport as QCReportType, QCIssue } from '../types';
import { IssueResolver, BatchAutoFix } from './IssueResolver';

interface QCReportProps {
  report: QCReportType;
  jobId: string;
  onReportUpdated?: () => void;
}

export function QCReport({ report, jobId, onReportUpdated }: QCReportProps) {
  const { summary, issues } = report;
  const [selectedIssue, setSelectedIssue] = useState<QCIssue | null>(null);
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());

  const handleFixApplied = () => {
    setSelectedIssue(null);
    if (onReportUpdated) {
      onReportUpdated();
    }
  };

  const toggleType = (type: string) => {
    const newExpanded = new Set(expandedTypes);
    if (newExpanded.has(type)) {
      newExpanded.delete(type);
    } else {
      newExpanded.add(type);
    }
    setExpandedTypes(newExpanded);
  };

  // Group issues by type
  const issuesByType: Record<string, QCIssue[]> = {};
  for (const issue of issues) {
    const type = issue.issue_type;
    if (!issuesByType[type]) {
      issuesByType[type] = [];
    }
    issuesByType[type].push(issue);
  }

  return (
    <div className="qc-report">
      <div className={`qc-summary ${summary.passed ? 'passed' : 'failed'}`}>
        <div className="summary-header">
          <span className="status-icon">{summary.passed ? '✓' : '✗'}</span>
          <span className="status-text">
            {summary.passed ? 'QC Passed' : 'QC Failed - Review Required'}
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

      {/* Batch auto-fix buttons */}
      {!summary.passed && Object.keys(issuesByType).length > 0 && (
        <div className="batch-actions">
          <h4>Quick Actions</h4>
          <div className="batch-buttons">
            <BatchAutoFix
              jobId={jobId}
              issueCount={issues.length}
              onComplete={handleFixApplied}
            />
            {Object.entries(summary.by_type).map(([type, count]) => (
              <BatchAutoFix
                key={type}
                jobId={jobId}
                issueType={type}
                issueCount={count}
                onComplete={handleFixApplied}
              />
            ))}
          </div>
        </div>
      )}

      {/* Issues grouped by type */}
      {Object.keys(issuesByType).length > 0 && (
        <div className="issues-by-type-detailed">
          <h4>Issues by Type</h4>
          {Object.entries(issuesByType).map(([type, typeIssues]) => (
            <div key={type} className="issue-type-group">
              <div
                className="type-header"
                onClick={() => toggleType(type)}
              >
                <span className="expand-icon">
                  {expandedTypes.has(type) ? '▼' : '▶'}
                </span>
                <span className="issue-type">{type.replace(/_/g, ' ')}</span>
                <span className="issue-count">{typeIssues.length}</span>
              </div>
              
              {expandedTypes.has(type) && (
                <div className="type-issues">
                  {typeIssues.map((issue, i) => (
                    <div
                      key={i}
                      className={`issue-item ${issue.severity}`}
                    >
                      <div className="issue-info">
                        <span className="issue-cue">Cue {issue.cue_index}</span>
                        <span className="issue-message">{issue.message}</span>
                      </div>
                      <button
                        className="btn-fix"
                        onClick={() => setSelectedIssue(issue)}
                      >
                        Fix
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* All issues list (collapsed by default) */}
      {issues.length > 0 && (
        <div className="issues-list">
          <h4>All Issues ({issues.length})</h4>
          <div className="issues-scroll">
            {issues.slice(0, 50).map((issue, i) => (
              <div
                key={i}
                className={`issue-item ${issue.severity}`}
              >
                <div className="issue-info">
                  <span className="issue-cue">Cue {issue.cue_index}</span>
                  <span className="issue-message">{issue.message}</span>
                </div>
                <button
                  className="btn-fix"
                  onClick={() => setSelectedIssue(issue)}
                >
                  Fix
                </button>
              </div>
            ))}
            {issues.length > 50 && (
              <p className="issues-more">
                ... and {issues.length - 50} more issues. Use batch auto-fix above.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Issue resolver modal */}
      {selectedIssue && (
        <div className="issue-resolver-overlay">
          <IssueResolver
            jobId={jobId}
            issue={selectedIssue}
            onFixApplied={handleFixApplied}
            onClose={() => setSelectedIssue(null)}
          />
        </div>
      )}
    </div>
  );
}
