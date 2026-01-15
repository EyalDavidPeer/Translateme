import { useState } from 'react';
import type { GenderForm, GenderAlternative, QCSummary } from '../types';
import { setSegmentGender, batchSetGender } from '../api/client';

interface GenderToggleProps {
  jobId: string;
  cueIndex: number;
  currentText: string;
  activeGender: GenderForm;
  confidence: number;
  alternatives: GenderAlternative[];
  onGenderChanged: (newText: string, newGender: GenderForm) => void;
}

export function GenderToggle({
  jobId,
  cueIndex,
  currentText,
  activeGender,
  confidence,
  alternatives,
  onGenderChanged,
}: GenderToggleProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenderChange = async (gender: GenderForm) => {
    if (gender === activeGender) return;

    try {
      setLoading(true);
      setError(null);
      const result = await setSegmentGender(jobId, cueIndex, gender);
      onGenderChanged(result.new_text, result.new_gender);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to change gender');
    } finally {
      setLoading(false);
    }
  };

  if (!alternatives || alternatives.length < 2) {
    return null;
  }

  const masculineAlt = alternatives.find(a => a.gender === 'masculine');
  const feminineAlt = alternatives.find(a => a.gender === 'feminine');

  return (
    <div className="gender-toggle">
      <div className="gender-header">
        <span className="gender-label">Gender:</span>
        <span className={`gender-confidence ${confidence < 0.7 ? 'low' : 'high'}`}>
          {Math.round(confidence * 100)}% confident
        </span>
      </div>

      <div className="gender-buttons">
        {masculineAlt && (
          <button
            className={`gender-btn masculine ${activeGender === 'masculine' ? 'active' : ''}`}
            onClick={() => handleGenderChange('masculine')}
            disabled={loading}
            title={masculineAlt.text}
          >
            ♂ Masculine
          </button>
        )}
        {feminineAlt && (
          <button
            className={`gender-btn feminine ${activeGender === 'feminine' ? 'active' : ''}`}
            onClick={() => handleGenderChange('feminine')}
            disabled={loading}
            title={feminineAlt.text}
          >
            ♀ Feminine
          </button>
        )}
      </div>

      {error && <div className="gender-error">{error}</div>}

      <div className="gender-previews">
        {masculineAlt && (
          <div className={`gender-preview ${activeGender === 'masculine' ? 'active' : ''}`}>
            <span className="preview-label">♂</span>
            <span className="preview-text" dir="auto">{masculineAlt.text}</span>
          </div>
        )}
        {feminineAlt && (
          <div className={`gender-preview ${activeGender === 'feminine' ? 'active' : ''}`}>
            <span className="preview-label">♀</span>
            <span className="preview-text" dir="auto">{feminineAlt.text}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// Batch gender selector for QC report
interface BatchGenderSelectorProps {
  jobId: string;
  ambiguousCount: number;
  onBatchApplied: () => void;
}

export function BatchGenderSelector({
  jobId,
  ambiguousCount,
  onBatchApplied,
}: BatchGenderSelectorProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ count: number; gender: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleBatchSet = async (gender: GenderForm) => {
    try {
      setLoading(true);
      setError(null);
      const response = await batchSetGender(jobId, gender);
      setResult({ count: response.updated_count, gender });
      onBatchApplied();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to batch set gender');
    } finally {
      setLoading(false);
    }
  };

  if (ambiguousCount === 0) return null;

  return (
    <div className="batch-gender-selector">
      <span className="batch-label">
        Set all uncertain ({ambiguousCount}) to:
      </span>
      <div className="batch-buttons">
        <button
          className="gender-btn masculine small"
          onClick={() => handleBatchSet('masculine')}
          disabled={loading}
        >
          ♂ Male
        </button>
        <button
          className="gender-btn feminine small"
          onClick={() => handleBatchSet('feminine')}
          disabled={loading}
        >
          ♀ Female
        </button>
      </div>

      {result && (
        <span className="batch-result">
          ✓ Set {result.count} to {result.gender}
        </span>
      )}
      {error && <span className="batch-error">{error}</span>}
    </div>
  );
}

// Inline gender indicator for subtitle preview
interface GenderIndicatorProps {
  activeGender: GenderForm;
  confidence: number;
  hasAlternatives: boolean;
  onClick?: () => void;
}

export function GenderIndicator({
  activeGender,
  confidence,
  hasAlternatives,
  onClick,
}: GenderIndicatorProps) {
  if (!hasAlternatives) return null;

  const isAmbiguous = confidence < 0.7;
  const genderIcon = activeGender === 'masculine' ? '♂' : activeGender === 'feminine' ? '♀' : '?';

  return (
    <button
      className={`gender-indicator ${isAmbiguous ? 'ambiguous' : ''} ${activeGender}`}
      onClick={onClick}
      title={`Gender: ${activeGender} (${Math.round(confidence * 100)}% confident)${isAmbiguous ? ' - Click to change' : ''}`}
    >
      {genderIcon}
      {isAmbiguous && <span className="ambiguous-dot"></span>}
    </button>
  );
}
