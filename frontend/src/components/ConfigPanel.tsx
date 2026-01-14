import type { JobConstraints } from '../types';

interface ConfigPanelProps {
  targetLang: string;
  setTargetLang: (lang: string) => void;
  constraints: JobConstraints;
  setConstraints: (constraints: JobConstraints) => void;
  dryRun: boolean;
  setDryRun: (dryRun: boolean) => void;
  disabled?: boolean;
}

const LANGUAGES = [
  { code: 'he', name: 'Hebrew' },
  { code: 'ar', name: 'Arabic' },
  { code: 'es', name: 'Spanish' },
  { code: 'fr', name: 'French' },
  { code: 'de', name: 'German' },
  { code: 'it', name: 'Italian' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'ru', name: 'Russian' },
  { code: 'zh', name: 'Chinese' },
  { code: 'ja', name: 'Japanese' },
  { code: 'ko', name: 'Korean' },
];

export function ConfigPanel({
  targetLang,
  setTargetLang,
  constraints,
  setConstraints,
  dryRun,
  setDryRun,
  disabled,
}: ConfigPanelProps) {
  return (
    <div className="config-panel">
      <h3>Translation Settings</h3>
      
      <div className="config-group">
        <label htmlFor="target-lang">Target Language</label>
        <select
          id="target-lang"
          value={targetLang}
          onChange={(e) => setTargetLang(e.target.value)}
          disabled={disabled}
        >
          {LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.name}
            </option>
          ))}
        </select>
      </div>

      <h3>Constraints</h3>

      <div className="config-row">
        <div className="config-group">
          <label htmlFor="max-lines">Max Lines</label>
          <input
            id="max-lines"
            type="number"
            min={1}
            max={4}
            value={constraints.max_lines}
            onChange={(e) =>
              setConstraints({ ...constraints, max_lines: parseInt(e.target.value) || 2 })
            }
            disabled={disabled}
          />
        </div>

        <div className="config-group">
          <label htmlFor="max-chars">Max Chars/Line</label>
          <input
            id="max-chars"
            type="number"
            min={20}
            max={80}
            value={constraints.max_chars_per_line}
            onChange={(e) =>
              setConstraints({
                ...constraints,
                max_chars_per_line: parseInt(e.target.value) || 42,
              })
            }
            disabled={disabled}
          />
        </div>
      </div>

      <div className="config-row">
        <div className="config-group">
          <label htmlFor="max-cps">Max CPS</label>
          <input
            id="max-cps"
            type="number"
            min={10}
            max={30}
            step={0.5}
            value={constraints.max_cps}
            onChange={(e) =>
              setConstraints({ ...constraints, max_cps: parseFloat(e.target.value) || 17 })
            }
            disabled={disabled}
          />
        </div>

        <div className="config-group">
          <label htmlFor="min-duration">Min Duration (ms)</label>
          <input
            id="min-duration"
            type="number"
            min={100}
            max={2000}
            step={100}
            value={constraints.min_duration_ms}
            onChange={(e) =>
              setConstraints({
                ...constraints,
                min_duration_ms: parseInt(e.target.value) || 500,
              })
            }
            disabled={disabled}
          />
        </div>
      </div>

      <div className="config-group checkbox-group">
        <label>
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            disabled={disabled}
          />
          <span>Dry Run (parse + QC only, no translation)</span>
        </label>
      </div>
    </div>
  );
}
