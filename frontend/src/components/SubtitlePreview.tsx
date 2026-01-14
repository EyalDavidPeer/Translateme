import type { SubtitleSegment } from '../types';

interface SubtitlePreviewProps {
  segments: SubtitleSegment[];
}

function formatTime(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  
  const ss = (seconds % 60).toString().padStart(2, '0');
  const mm = (minutes % 60).toString().padStart(2, '0');
  const hh = hours.toString().padStart(2, '0');
  const mmm = (ms % 1000).toString().padStart(3, '0');
  
  return `${hh}:${mm}:${ss}.${mmm}`;
}

function getQCFlagClass(flags: string[]): string {
  if (flags.some(f => f.includes('exceeded') || f.includes('too_long') || f.includes('too_many'))) {
    return 'qc-error';
  }
  if (flags.length > 0) {
    return 'qc-warning';
  }
  return '';
}

export function SubtitlePreview({ segments }: SubtitlePreviewProps) {
  if (segments.length === 0) {
    return (
      <div className="preview-empty">
        <p>No subtitles to preview. Upload a file and run translation.</p>
      </div>
    );
  }

  return (
    <div className="subtitle-preview">
      <table>
        <thead>
          <tr>
            <th className="col-index">#</th>
            <th className="col-time">Time</th>
            <th className="col-original">Original</th>
            <th className="col-translated">Translated</th>
            <th className="col-qc">QC</th>
          </tr>
        </thead>
        <tbody>
          {segments.map((segment) => (
            <tr key={segment.index} className={getQCFlagClass(segment.qc_flags)}>
              <td className="col-index">{segment.index}</td>
              <td className="col-time">
                <span className="time-range">
                  {formatTime(segment.start_ms)}
                  <br />
                  {formatTime(segment.end_ms)}
                </span>
              </td>
              <td className="col-original">
                <pre>{segment.text}</pre>
              </td>
              <td className="col-translated">
                <pre dir="auto">{segment.translated_text || '—'}</pre>
              </td>
              <td className="col-qc">
                {segment.qc_flags.length > 0 ? (
                  <ul className="qc-flags">
                    {segment.qc_flags.map((flag, i) => (
                      <li key={i}>{flag.replace(/_/g, ' ')}</li>
                    ))}
                  </ul>
                ) : (
                  <span className="qc-ok">✓</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
