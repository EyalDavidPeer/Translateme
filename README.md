# Auto Subtitle Localization Platform

A B2B platform for streaming companies to automatically localize subtitle files (SRT/VTT) with high-quality translations, enforced constraints, and comprehensive QC reporting.

## Features

- **Multi-format Support**: Parse and export SRT and WebVTT subtitle files
- **Context-aware Translation**: Uses sliding context window for coherent translations
- **Constraint Enforcement**: 
  - Maximum characters per line (default: 42)
  - Maximum lines per cue (default: 2)  
  - Maximum reading speed in CPS (default: 17)
  - Automatic text condensation when constraints are violated
- **Smart Line Breaking**: Punctuation-aware line wrapping
- **Glossary Support**: Maintain consistent terminology across translations
- **QC Reporting**: Comprehensive quality checks with detailed reports
- **Dry Run Mode**: Validate files without translation

## Architecture

```
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── parsing/        # SRT/VTT parsers
│   │   ├── translation/    # Translation providers
│   │   ├── postprocess/    # Line wrapping, condensation
│   │   ├── qc/            # Quality control checks
│   │   └── export/        # SRT/VTT exporters
│   └── tests/              # Unit tests
├── frontend/               # React dashboard
│   └── src/
│       ├── components/     # UI components
│       ├── hooks/         # React hooks
│       └── api/           # API client
└── examples/              # Sample files
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key (for real translations)

## Quick Start

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment (IMPORTANT!)

**You MUST configure your OpenAI API key for real translations to work!**

1. Copy the example file:
   ```bash
   # Windows:
   copy backend\env_example.txt backend\.env
   # macOS/Linux:
   cp backend/env_example.txt backend/.env
   ```

2. Edit `backend/.env` and add your OpenAI API key:
   ```env
   # Get your key from: https://platform.openai.com/api-keys
   OPENAI_API_KEY=sk-your-actual-api-key-here
   TRANSLATION_PROVIDER=openai
   OPENAI_MODEL=gpt-4o
   ```

⚠️ **Without a valid API key, the system uses a Mock provider that doesn't actually translate!**

### 3. Run Backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The dashboard will be available at http://localhost:5173

## Usage

### Web Dashboard

1. Open http://localhost:5173 in your browser
2. Upload an SRT or VTT file
3. Select target language (Hebrew by default)
4. Adjust constraints if needed
5. Click "Start Translation"
6. Preview results and download translated files

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /api/jobs` | Create translation job |
| `GET /api/jobs/{job_id}` | Get job status and progress |
| `GET /api/jobs/{job_id}/result` | Get translated segments and QC report |
| `GET /api/jobs/{job_id}/download/{format}` | Download SRT or VTT file |
| `GET /api/jobs/{job_id}/qc-report` | Download QC report JSON |

### Example API Usage

```bash
# Create a translation job
curl -X POST http://localhost:8000/api/jobs \
  -F "file=@examples/sample_english.srt" \
  -F "target_lang=he" \
  -F "max_chars_per_line=42" \
  -F "max_cps=17"

# Response: {"job_id": "abc123..."}

# Check job status
curl http://localhost:8000/api/jobs/abc123

# Download translated SRT
curl -O http://localhost:8000/api/jobs/abc123/download/srt
```

## Running Tests

```bash
cd backend
pytest -v
```

## Configuration Options

### Job Constraints

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `max_lines` | 2 | 1-4 | Maximum lines per subtitle cue |
| `max_chars_per_line` | 42 | 20-80 | Maximum characters per line |
| `max_cps` | 17 | 10-30 | Maximum characters per second (reading speed) |
| `min_duration_ms` | 500 | 100-2000 | Minimum cue duration in milliseconds |

### Translation Providers

- **Mock Provider**: Returns original text with language prefix (for testing)
- **OpenAI Provider**: Uses GPT-4o for high-quality translations

Set `TRANSLATION_PROVIDER=openai` in your environment to use OpenAI.

## QC Checks

The platform performs the following quality checks:

| Check | Severity | Description |
|-------|----------|-------------|
| CPS Exceeded | Error | Reading speed too fast |
| Line Too Long | Error | Characters exceed limit |
| Too Many Lines | Error | More than allowed lines |
| Empty Cue | Warning | No text content |
| Overlap | Warning | Timing overlaps with next cue |
| Short Duration | Warning | Cue duration too brief |

## Glossary Format

Create a JSON file with term mappings:

```json
{
  "Queen": "המלכה",
  "Professor": "פרופסור",
  "CEO": "מנכ\"ל"
}
```

Pass the glossary content as a JSON string in the `glossary` form field.

## Project Structure

### Backend Modules

- **parsing/**: SRT and VTT file parsers with timestamp handling
- **translation/**: Pluggable translation providers (Mock, OpenAI)
- **postprocess/**: Line wrapping and text condensation
- **qc/**: Quality control checks and reporting
- **export/**: SRT and VTT file generation

### Frontend Components

- **FileUpload**: Drag-and-drop file upload
- **ConfigPanel**: Language and constraint settings
- **SubtitlePreview**: Side-by-side comparison table
- **QCReport**: Quality check results display
- **DownloadPanel**: Export buttons for SRT/VTT/JSON

## Development

### Adding a New Translation Provider

1. Create a new file in `backend/app/translation/`
2. Implement the `TranslationProvider` interface
3. Add provider initialization in `job_runner.py`

### Extending QC Checks

1. Add check function in `backend/app/qc/checks.py`
2. Add new issue type to `QCIssueType` enum
3. Call the check in `run_qc_checks()`

## License

MIT License - see LICENSE file for details.

## Support

For issues and feature requests, please open a GitHub issue.
