import type { SubtitleSegment } from '../types';
import { GenderIndicator } from './GenderToggle';

interface SubtitlePreviewProps {
  segments: SubtitleSegment[];
  onGenderClick?: (segment: SubtitleSegment) => void;
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

// Categorize flags into errors, auto-fixed, and manual fixes
function categorizeFlags(flags: string[]): { errors: string[]; autoFixed: string[]; manualFixed: string[] } {
  const errors: string[] = [];
  const autoFixed: string[] = [];
  const manualFixed: string[] = [];
  
  for (const flag of flags) {
    if (flag.startsWith('CONFORMED:')) {
      autoFixed.push(flag);
    } else if (flag.startsWith('FIXED:')) {
      manualFixed.push(flag);
    } else if (flag !== 'UNFIXABLE') {
      // Actual errors: cps_exceeded, line_too_long, too_many_lines, etc.
      errors.push(flag);
    } else {
      errors.push(flag); // UNFIXABLE is still an error
    }
  }
  
  return { errors, autoFixed, manualFixed };
}

function getQCFlagClass(flags: string[]): string {
  const { errors, autoFixed, manualFixed } = categorizeFlags(flags);
  
  // If there are actual errors, show as error
  if (errors.length > 0) {
    return 'qc-error';
  }
  // If only auto-fixed, show as success
  if (autoFixed.length > 0) {
    return 'qc-auto-fixed';
  }
  // If manually fixed, show as fixed
  if (manualFixed.length > 0) {
    return 'qc-manual-fixed';
  }
  return '';
}

function getFlagBadgeClass(flag: string): string {
  if (flag.startsWith('CONFORMED:')) {
    return 'flag-auto-fixed';
  }
  if (flag.startsWith('FIXED:')) {
    return 'flag-manual-fixed';
  }
  if (flag === 'UNFIXABLE') {
    return 'flag-unfixable';
  }
  return 'flag-error';
}

function formatFlagLabel(flag: string): string {
  if (flag.startsWith('CONFORMED:')) {
    const action = flag.replace('CONFORMED:', '').toLowerCase();
    return `✓ Auto: ${action}`;
  }
  if (flag.startsWith('FIXED:')) {
    const action = flag.replace('FIXED:', '').toLowerCase();
    return `✓ Fixed: ${action}`;
  }
  return flag.replace(/_/g, ' ');
}

export function SubtitlePreview({ segments, onGenderClick }: SubtitlePreviewProps) {
  if (segments.length === 0) {
    return (
      <div className="preview-empty">
        <p>No subtitles to preview. Upload a file and run translation.</p>
      </div>
    );
  }

  const hasAnyGenderAlternatives = segments.some(
    seg => seg.gender_alternatives && seg.gender_alternatives.length > 1
  );

  return (
    <div className="subtitle-preview">
      <table>
        <thead>
          <tr>
            <th className="col-index">#</th>
            <th className="col-time">Time</th>
            <th className="col-original">Original</th>
            <th className="col-translated">Translated</th>
            {hasAnyGenderAlternatives && <th className="col-gender">Gender</th>}
            <th className="col-qc">QC</th>
          </tr>
        </thead>
        <tbody>
          {segments.map((segment) => {
            const hasGenderAlts = segment.gender_alternatives && segment.gender_alternatives.length > 1;
            
            return (
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
                {hasAnyGenderAlternatives && (
                  <td className="col-gender">
                    {hasGenderAlts && (
                      <GenderIndicator
                        activeGender={segment.active_gender || 'unknown'}
                        confidence={segment.gender_confidence || 1}
                        hasAlternatives={true}
                        onClick={onGenderClick ? () => onGenderClick(segment) : undefined}
                      />
                    )}
                  </td>
                )}
                <td className="col-qc">
                  {segment.qc_flags.length > 0 ? (
                    <ul className="qc-flags">
                      {segment.qc_flags.map((flag, i) => (
                        <li key={i} className={getFlagBadgeClass(flag)}>
                          {formatFlagLabel(flag)}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span className="qc-ok">✓</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
