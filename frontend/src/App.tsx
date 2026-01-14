import { useState } from 'react';
import { FileUpload } from './components/FileUpload';
import { ConfigPanel } from './components/ConfigPanel';
import { SubtitlePreview } from './components/SubtitlePreview';
import { QCReport } from './components/QCReport';
import { DownloadPanel } from './components/DownloadPanel';
import { useJob } from './hooks/useJob';
import type { JobConstraints, JobConfig } from './types';
import './App.css';

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [targetLang, setTargetLang] = useState('he');
  const [constraints, setConstraints] = useState<JobConstraints>({
    max_lines: 2,
    max_chars_per_line: 42,
    max_cps: 17,
    min_duration_ms: 500,
  });
  const [dryRun, setDryRun] = useState(false);

  const { jobId, status, result, isLoading, error, startJob, reset } = useJob();

  const handleFileSelect = (selectedFile: File) => {
    setFile(selectedFile);
    reset();
  };

  const handleSubmit = async () => {
    if (!file) return;

    const config: JobConfig = {
      source_lang: 'en',
      target_lang: targetLang,
      constraints,
      glossary: {},
      dry_run: dryRun,
    };

    await startJob(file, config);
  };

  const handleNewJob = () => {
    setFile(null);
    reset();
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/>
            <path d="M2 12h20"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
          <h1>SubLocalize</h1>
        </div>
        <p className="tagline">Professional Subtitle Localization Platform</p>
      </header>

      <main className="app-main">
        {!result ? (
          <div className="setup-panel">
            <div className="upload-section">
              <FileUpload
                onFileSelect={handleFileSelect}
                disabled={isLoading}
              />
            </div>

            <div className="config-section">
              <ConfigPanel
                targetLang={targetLang}
                setTargetLang={setTargetLang}
                constraints={constraints}
                setConstraints={setConstraints}
                dryRun={dryRun}
                setDryRun={setDryRun}
                disabled={isLoading}
              />

              <button
                className="submit-btn"
                onClick={handleSubmit}
                disabled={!file || isLoading}
              >
                {isLoading ? 'Processing...' : dryRun ? 'Run QC Check' : 'Start Translation'}
              </button>

              {error && (
                <div className="error-message">
                  <strong>Error:</strong> {error}
                </div>
              )}
            </div>

            {status && (
              <div className="progress-section">
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${status.progress}%` }}
                  />
                </div>
                <p className="progress-text">
                  {status.status === 'processing'
                    ? `Processing: ${Math.round(status.progress)}%`
                    : status.status === 'pending'
                    ? 'Starting...'
                    : status.status}
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="results-panel">
            <div className="results-header">
              <h2>Translation Complete</h2>
              <button className="new-job-btn" onClick={handleNewJob}>
                ← New Translation
              </button>
            </div>

            <div className="results-content">
              <div className="results-left">
                <SubtitlePreview segments={result.segments} />
              </div>
              <div className="results-right">
                <QCReport report={result.qc_report} />
                {jobId && <DownloadPanel jobId={jobId} />}
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="app-footer">
        <p>Auto Subtitle Localization Platform &copy; 2026</p>
      </footer>
    </div>
  );
}

export default App;
