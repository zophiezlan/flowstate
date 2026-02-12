# Contributing to FlowState

Thank you for your interest in improving FlowState!

## Quick Links

- **Report bugs:** [GitHub Issues](https://github.com/zophiezlan/flowstate/issues)
- **Suggest features:** Open an issue with `[Feature Request]` in the title
- **Documentation:** [docs/](docs/) folder

---

## Development Setup

### Prerequisites

- Python 3.9+
- Git
- (Optional) Raspberry Pi Zero 2 W with PN532 for hardware testing

### Initial Setup

```bash
# Clone repository
git clone https://github.com/zophiezlan/flowstate.git
cd flowstate

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies (formatters, linters, etc.)
pip install -r requirements-dev.txt

# Copy example config
cp config.yaml.example config.yaml

# Run tests
pytest -v
```

---

## Project Structure

```
flowstate/
├── tap_station/           # Core application
│   ├── main.py           # Service entry point
│   ├── config.py         # Configuration management
│   ├── database.py       # SQLite operations
│   ├── nfc_reader.py     # NFC reader wrapper
│   ├── web_server.py     # Flask server (dashboards, API, control panel)
│   ├── extension.py      # Extension base class & TapEvent protocol
│   ├── registry.py       # Extension loader & hook dispatcher
│   ├── feedback.py       # Buzzer/LED control
│   ├── validation.py     # Event sequence validation
│   ├── anomaly_detector.py # Anomaly detection
│   ├── service_integration.py # Service workflow integration
│   ├── health.py         # System health monitoring
│   ├── failover_manager.py # Multi-station failover
│   └── templates/        # 11 Jinja2 HTML templates
├── extensions/            # Modular feature plugins (12 extensions)
│   ├── anomalies/        # Real-time anomaly alerting
│   ├── event_summary/    # End-of-day summary reports
│   ├── export/           # CSV/JSON data export
│   ├── hardware_monitor/ # Raspberry Pi hardware health
│   ├── insights/         # Service quality metrics (SLI/SLO)
│   ├── manual_corrections/ # Manual event add/remove
│   ├── notes/            # Operational notes
│   ├── shift_summary/    # Shift handoff reports
│   ├── smart_estimates/  # Wait time prediction
│   ├── stuck_cards/      # Stuck card detection & force-exit
│   ├── substance_tracking/ # Substance return tracking
│   └── three_stage/      # 3-stage queue/service tracking
├── scripts/              # Utility & setup scripts
├── mobile_app/           # Offline-first Android PWA
├── tests/                # Pytest test suite
├── examples/             # Example service configurations
├── docs/                 # Documentation
└── data/                 # SQLite database storage
```

See [docs/EXTENSIONS.md](docs/EXTENSIONS.md) for details on creating and configuring extensions.

---

## Code Standards

### Style Guide

**Python:**

- Follow PEP 8
- Use type hints where helpful
- Max line length: 79 characters (configured in `pyproject.toml`)
- Use descriptive variable names
- Sort imports with `isort`

**Markdown/YAML:**

- Consistent formatting with `prettier`
- Clear headings and structure
- Code blocks with language tags

### Automated Formatting

```bash
# Windows (PowerShell)
.\scripts\format.ps1

# Windows (Command Prompt)
scripts\format.bat

# Linux/Mac/WSL
./scripts/format.sh
```

These scripts will:

- Format Python files with `black` (line length: 79)
- Sort imports with `isort` (compatible with black)
- Format Markdown, YAML, JSON with `prettier`

**Check formatting without modifying:**

```bash
black . --check
isort . --check-only
prettier --check "**/*.{md,yaml,yml,json}"
```

See [scripts/README_FORMATTING.md](scripts/README_FORMATTING.md) for detailed formatting documentation.

### Configuration Files

- `pyproject.toml` - Python tool configuration (black, isort, pytest, mypy)
- `.prettierrc.json` - Prettier configuration
- `.prettierignore` - Files to exclude from prettier

### Imports

```python
# Standard library
import sys
import logging
from pathlib import Path

# Third party
from flask import Flask
import yaml

# Local
from tap_station.config import Config
from tap_station.database import Database
```

---

## Testing

### Running Tests

```bash
# All tests
pytest -v

# Specific file
pytest tests/test_database.py -v

# With coverage
pytest --cov=tap_station tests/

# Skip integration tests (require hardware)
pytest -m "not integration"
```

### Writing Tests

- Write tests for all new features
- Aim for high coverage (>80%)
- Use descriptive test names
- Use fixtures for common setup
- Mock hardware dependencies (NFC reader, GPIO)

---

## Making Changes

### Development Workflow

1. **Create a branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes** - Write code, add/update tests, update documentation

3. **Test locally**

   ```bash
   pytest -v
   python -m tap_station.main --mock-nfc  # Test without hardware
   ```

4. **Format and lint**

   ```bash
   black tap_station tests scripts --line-length 79
   flake8 tap_station/ tests/ scripts/
   ```

5. **Commit and push**

   ```bash
   git add .
   git commit -m "feat: brief description"
   git push origin feature/your-feature-name
   ```

### Commit Messages

Use [conventional commits](https://www.conventionalcommits.org/) format:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, no code change
- `refactor`: Code restructuring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

---

## Creating Extensions

Extensions are the preferred way to add new features. See [docs/EXTENSIONS.md](docs/EXTENSIONS.md) for the full guide.

Quick overview:

1. Create `extensions/your_feature/__init__.py`
2. Subclass `Extension` from `tap_station.extension`
3. Override the hooks you need (`on_tap`, `on_startup`, `on_api_routes`, etc.)
4. Export an `extension` instance or `create()` factory
5. Add `"your_feature"` to `extensions.enabled` in `config.yaml`

---

## Areas for Contribution

### High Priority

- **Extension development** - New extensions for additional features
- **Mobile app improvements** - Better error handling, UI polish
- **Data analysis scripts** - Python/R scripts for analyzing wait times
- **Testing** - More integration tests, extension tests

### Good First Issues

- Documentation improvements
- Error message clarity
- Example configurations
- Troubleshooting scenarios

---

## Code Review Guidelines

### For Contributors

- Ensure tests pass
- Update documentation
- Keep PRs focused (one feature/fix per PR)
- Respond to feedback promptly

### For Reviewers

- Review within 3 days if possible
- Be constructive and specific
- Approve when "good enough"
- Merge when approved and tests pass

---

## Security

### Reporting Security Issues

**Do not** open public issues for security vulnerabilities. Instead:

- Provide detailed description via private channels
- Allow reasonable time for fix before disclosure

### Security Best Practices

- Validate all user inputs
- Use parameterized SQL queries (already implemented)
- Avoid storing sensitive data in logs
- Keep dependencies updated

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
