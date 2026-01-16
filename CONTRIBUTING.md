# Contributing to NFC Tap Logger

Thank you for considering contributing to NFC Tap Logger! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Git
- (Optional) Raspberry Pi Zero 2 W with PN532 NFC reader for hardware testing

### Initial Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/zophiezlan/nfc-tap-logger.git
   cd nfc-tap-logger
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Create your config file**

   ```bash
   cp config.yaml.example config.yaml
   # Edit config.yaml as needed
   ```

5. **Run tests**
   ```bash
   pytest -v
   ```

## Code Standards

### Style Guide

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
nfc-tap-logger/
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
