# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Omnis is a modular Linux installer (Calamares alternative) using Python 3.11+ and PySide6/Qt6 with QML interface.

## Commands

```bash
# Install dependencies (dev mode)
pip install -e ".[dev]"

# Run all tests
pytest

# Run single test file
pytest tests/unit/test_engine.py

# Run single test
pytest tests/unit/test_engine.py::test_function_name -v

# Type checking
mypy src/

# Linting and formatting
ruff check src/
ruff format src/

# Run the installer (debug mode)
python -m omnis.main --debug

# Run with specific config
python -m omnis.main --config config/examples/glfos.yaml --debug
```

## Architecture

### Security Model: UI/Engine Separation

The installer uses strict process separation for security:

- **UI Process** (user context): QML interface, user interactions, no privileged access
- **Engine Process** (root context): Job execution, system operations, privileged commands
- **IPC**: Unix socket with JSON messages (planned - currently direct bridge)

### Core Components

**Engine** (`src/omnis/core/engine.py`):
- Loads and validates YAML config via Pydantic models
- Orchestrates Jobs sequentially
- Callbacks: `on_job_start`, `on_job_progress`, `on_job_complete`, `on_error`
- Factory method: `Engine.from_config_file(path)`

**Jobs** (`src/omnis/jobs/`):
- `BaseJob`: Abstract base with `run()`, `validate()`, `cleanup()`, `estimate_duration()`
- `JobContext`: Passed to jobs with `target_root`, `selections`, `config`, progress callback
- `JobResult`: Immutable result with `ok()` and `fail()` factory methods
- Jobs loaded dynamically from `omnis.jobs.<name>` (currently placeholder)

**GUI Bridge** (`src/omnis/gui/bridge.py`):
- `BrandingProxy`: Exposes branding config to QML as Qt Properties
- `EngineBridge`: Qt Signals/Slots connecting QML to Engine
- Asset paths resolved to `file://` URLs via `_resolve_asset()`

### Configuration System

Config files (`config/examples/*.yaml`) define:
- `branding`: Name, colors, strings, fonts, asset references
- `jobs`: Ordered list of installation steps with per-job config
- `theme`: Relative path to theme directory containing assets

Theme directories (`config/themes/<name>/`) contain:
- `logos/`, `wallpapers/`, `boot/` asset directories
- `theme.yaml` metadata

Asset resolution: Config file path → theme path → asset relative path → absolute `file://` URL

### Data Flow

```
omnis.yaml → Engine → Jobs[] → Execute sequentially
                ↓
         BrandingProxy → QML Properties
                ↓
         EngineBridge ← QML Signals/Slots
```

## Pydantic Models Hierarchy

```
OmnisConfig
├── BrandingConfig
│   ├── BrandingColors
│   ├── BrandingAssets
│   ├── BrandingStrings
│   └── BrandingFonts
├── JobDefinition[]
└── AdvancedConfig
```

## Creating New Jobs

```python
# src/omnis/jobs/my_job.py
from omnis.jobs.base import BaseJob, JobContext, JobResult

class Job(BaseJob):
    name = "my_job"
    description = "Description"

    def run(self, context: JobContext) -> JobResult:
        context.report_progress(50, "Working...")
        return JobResult.ok("Done")

    def estimate_duration(self) -> int:
        return 30  # seconds
```

Then reference in config: `jobs: [{ name: my_job, config: {...} }]`

## Code Standards

- Type hints required (`strict = true` in mypy)
- Line length: 100 characters
- Ruff rules: E, W, F, I, B, C4, UP, ARG, SIM
- Language: Code in English, comments/docs may be in French
