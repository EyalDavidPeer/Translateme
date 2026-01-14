import { getDownloadUrl, getQCReportUrl } from '../api/client';

interface DownloadPanelProps {
  jobId: string;
}

export function DownloadPanel({ jobId }: DownloadPanelProps) {
  return (
    <div className="download-panel">
      <h3>Download Results</h3>
      <div className="download-buttons">
        <a
          href={getDownloadUrl(jobId, 'srt')}
          className="download-btn srt"
          download
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7,10 12,15 17,10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Download SRT
        </a>
        <a
          href={getDownloadUrl(jobId, 'vtt')}
          className="download-btn vtt"
          download
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7,10 12,15 17,10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Download VTT
        </a>
        <a
          href={getQCReportUrl(jobId)}
          className="download-btn qc"
          download
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14,2 14,8 20,8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          QC Report (JSON)
        </a>
      </div>
    </div>
  );
}
