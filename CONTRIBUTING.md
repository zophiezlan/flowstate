# Contributing to NFC Tap Logger

Thank you for your interest in improving NFC Tap Logger!

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
│   ├── feedback.py       # Buzzer/LED control
│   ├── web_server.py     # Flask status server
│   └── ndef_writer.py    # NDEF writing
├── scripts/              # Utility scripts
├── mobile_app/           # Progressive Web App
├── tests/                # Test suite
└── docs/                 # Documentation
```

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

**Format all code automatically:**

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

**Manual formatting:**

```bash
# Python only
black . --line-length 79
isort . --profile black --line-length 79

# Markdown/YAML only
prettier --write "**/*.{md,yaml,yml,json}"
```

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

# Check style

flake8 tap_station/ tests/ scripts/

````

**Imports:**

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
````

### Documentation

**Docstrings:**

```python
def log_event(token_id: str, stage: str, timestamp: datetime) -> bool:
    """
    Log an NFC tap event to the database.

    Args:
        token_id: Card token ID (e.g., "001")
        stage: Event stage (e.g., "QUEUE_JOIN", "EXIT")
        timestamp: Event timestamp (UTC)

    Returns:
        True if logged successfully, False if duplicate

    Raises:
        DatabaseError: If database write fails
    """
    ...
```

**Comments:**

- Explain _why_, not _what_
- Update comments when code changes
- Use TODO/FIXME/HACK markers for temporary code

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

**Unit tests:**

```python
def test_database_log_event(tmp_path):
    """Test logging events to database."""
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))

    result = db.log_event(
        token_id="001",
        uid="04abcdef",
        stage="QUEUE_JOIN",
        device_id="test",
        session_id="test-session"
    )

    assert result is True  # First tap
    assert db.get_event_count() == 1
```

**Mock NFC reader for tests:**

```python
from tap_station.nfc_reader import MockNFCReader

def test_with_mock_nfc():
    nfc = MockNFCReader()
    nfc.begin()

    # Simulate card tap
    success, uid = nfc.read_passive_target()
    assert success
    assert uid is not None
```

---

## Making Changes

### Development Workflow

1. **Create a branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes**
   - Write code
   - Add/update tests
   - Update documentation

3. **Test locally**

   ```bash
   pytest -v
   python -m tap_station.main --mock-nfc  # Test without hardware
   ```

4. **Commit**

   ```bash
   git add .
   git commit -m "Add feature: brief description"
   ```

5. **Push and create PR**

   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Messages

**Format:**

```
<type>: <brief summary>

<detailed description if needed>

<issue references>
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, no code change
- `refactor`: Code restructuring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

**Examples:**

```
feat: Add mobile app PWA support

Implements Progressive Web App for Android NFC scanning.
Includes offline storage, JSONL export, and ingest script.

Closes #42
```

```
fix: Handle I2C timeout gracefully

Catch I2C timeout exceptions and retry up to 3 times
before failing. Prevents service crash on transient errors.

Fixes #37
```

---

## Areas for Contribution

### High Priority

- **Mobile app improvements:** Better error handling, UI polish
- **Data analysis scripts:** Python/R scripts for analyzing wait times
- **Hardware guides:** Photos, diagrams, video tutorials
- **Testing:** More integration tests, hardware simulation

### Good First Issues

- Documentation improvements
- Code comments and docstrings
- Error message clarity
- Example configurations
- Troubleshooting scenarios

### Future Features

- Real-time dashboard during events
- Automated report generation
- Multi-language support
- iOS NFC support (when possible)
- Bluetooth card readers

---

## Documentation Guidelines

### When to Update Docs

- New features → Update relevant guides
- Bug fixes → Update troubleshooting if applicable
- API changes → Update docstrings and guides
- Configuration changes → Update config examples

### Documentation Structure

- **README.md** - Project overview, quick start
- **docs/SETUP.md** - Complete installation guide
- **docs/OPERATIONS.md** - Day-of-event workflow
- **docs/TROUBLESHOOTING.md** - Problem solving
- **docs/MOBILE.md** - Mobile app guide
- **CONTRIBUTING.md** - This file

---

## Release Process

**For maintainers:**

1. **Version bump**
   - Update version in `setup.py` (if exists)
   - Update `README.md` version history

2. **Changelog**
   - Document changes in README
   - Note breaking changes

3. **Tag release**

   ```bash
   git tag -a v1.2.0 -m "Release v1.2.0"
   git push origin v1.2.0
   ```

4. **GitHub release**
   - Create GitHub release from tag
   - Include changelog
   - Attach any binaries/assets

---

## Code Review Guidelines

### For Contributors

- Ensure tests pass
- Update documentation
- Keep PRs focused (one feature/fix per PR)
- Respond to feedback promptly
- Be respectful and professional

### For Reviewers

- Review within 3 days if possible
- Be constructive and specific
- Suggest improvements, don't demand perfection
- Approve when "good enough" (don't hold up for minor issues)
- Merge when approved and tests pass

---

## Getting Help

**Questions about contributing?**

- Open a GitHub issue with `[Question]` tag
- Check existing issues and PRs
- Review closed issues for similar questions

**Stuck on something?**

- Don't hesitate to ask for help
- We're friendly and want to support contributors
- Draft PRs are welcome for early feedback

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

- **PEP 8**: Follow Python's PEP 8 style guide
- **Line length**: Maximum 100 characters
- **Formatting**: Use `black` for automatic formatting
- **Linting**: Run `flake8` to check for issues

```bash
# Format code
black tap_station tests scripts

# Check style
flake8 tap_station tests scripts --max-line-length=100
```

### Type Hints

- Use type hints for function parameters and return values
- Use `Optional[Type]` for nullable values
- Use `List[Type]`, `Dict[K, V]` for collections

### Docstrings

- All public functions, classes, and modules must have docstrings
- Use Google-style docstrings format
- Include Args, Returns, and Raises sections where applicable

Example:

```python
def log_event(token_id: str, uid: str, stage: str) -> bool:
    """
    Log an NFC tap event to the database

    Args:
        token_id: Token identifier from card
        uid: Card UID in hex format
        stage: Event stage (e.g., "QUEUE_JOIN")

    Returns:
        True if logged successfully, False if duplicate

    Raises:
        DatabaseError: If database connection fails
    """
```

## Testing

### Running Tests

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=tap_station --cov-report=term-missing

# Run specific test file
pytest tests/test_web_server.py -v

# Run specific test
pytest tests/test_web_server.py::test_health_check -v
```

### Writing Tests

- Write tests for all new features
- Aim for high coverage (>80%)
- Use descriptive test names (e.g., `test_api_ingest_rejects_oversized_payloads`)
- Use fixtures for common setup
- Mock hardware dependencies (NFC reader, GPIO)

Example test:

```python
def test_duplicate_tap_returns_false(mock_db):
    """Test that duplicate taps are properly rejected"""
    # Setup
    mock_db.log_event.return_value = False

    # Execute
    result = station.handle_tap("ABC123", "001")

    # Assert
    assert result is False
```

## Pull Request Process

1. **Create a feature branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write code following the style guide
   - Add tests for new functionality
   - Update documentation as needed

3. **Run tests and linting**

   ```bash
   pytest -v
   black tap_station tests scripts
   flake8 tap_station tests scripts --max-line-length=100
   ```

4. **Commit your changes**

   ```bash
   git add .
   git commit -m "Add feature: brief description"
   ```

   Commit message guidelines:
   - Use present tense ("Add feature" not "Added feature")
   - Keep first line under 72 characters
   - Reference issues when applicable (#123)

5. **Push to your fork**

   ```bash
   git push origin feature/your-feature-name
   ```

6. **Open a Pull Request**
   - Provide a clear description of changes
   - Reference any related issues
   - Ensure CI passes
   - Request review from maintainers

## Issue Reporting

### Bug Reports

When reporting bugs, please include:

- **Description**: Clear description of the bug
- **Steps to reproduce**: Detailed steps
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Environment**: Python version, OS, hardware details
- **Logs**: Relevant log output

### Feature Requests

When requesting features, please include:

- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives**: Other options you've considered
- **Additional context**: Any other relevant information

## Code Review Guidelines

### For Contributors

- Be open to feedback
- Respond to review comments promptly
- Make requested changes or explain why you disagree
- Keep PRs focused and reasonably sized

### For Reviewers

- Be respectful and constructive
- Focus on code quality, not personal preferences
- Explain the reasoning behind suggestions
- Approve when changes meet standards

## Project Structure

```
flowstate/
├── tap_station/          # Main application code
│   ├── main.py          # Entry point and service loop
│   ├── config.py        # Configuration loader
│   ├── database.py      # SQLite operations
│   ├── nfc_reader.py    # NFC hardware interface
│   ├── feedback.py      # Buzzer/LED control
│   └── web_server.py    # Status web server
├── tests/               # Test suite
├── scripts/             # Utility scripts
├── docs/                # Documentation
├── mobile_app/          # Mobile web app
└── data/                # SQLite database storage
```

## Security

### Reporting Security Issues

**Do not** open public issues for security vulnerabilities. Instead:

- Email: [Your security contact email]
- Provide detailed description
- Allow reasonable time for fix before disclosure

### Security Best Practices

- Validate all user inputs
- Use parameterized SQL queries (already implemented)
- Avoid storing sensitive data in logs
- Keep dependencies updated

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see LICENSE file).

## Questions?

- Open a GitHub Discussion for questions
- Check existing issues and documentation
- Contact maintainers via GitHub

## Acknowledgments

Thank you for contributing to NFC Tap Logger! Your efforts help make this project better for everyone.
