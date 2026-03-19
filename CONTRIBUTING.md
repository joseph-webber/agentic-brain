# Contributing to Agentic Brain

Thank you for your interest in contributing to Agentic Brain! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

This project adheres to the Contributor Covenant Code of Conduct. By participating, you are expected to uphold this code. Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details.

## Getting Started

### Prerequisites

- Python 3.9+
- Git
- Poetry (for dependency management)

### Development Setup

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/agentic-brain.git
   cd agentic-brain
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/josephmcateer/agentic-brain.git
   ```
4. **Install dependencies**:
   ```bash
   poetry install
   ```
5. **Install pre-commit hooks** (optional but recommended):
   ```bash
   pre-commit install
   ```

## Making Changes

### Branch Strategy

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Use descriptive branch names:
   - `feature/add-memory-persistence` for features
   - `fix/resolve-memory-leak` for bug fixes
   - `docs/update-api-documentation` for documentation
   - `refactor/simplify-event-bus` for refactoring

### Code Style

This project enforces code quality through automated tools:

#### Python Formatting
- **Black**: Code formatter
  ```bash
  black src/ tests/
  ```
- **isort**: Import sorting
  ```bash
  isort src/ tests/
  ```
- **Ruff**: Linting
  ```bash
  ruff check src/ tests/
  ```

#### Type Hints
- All functions must have type hints
- Use `from typing import` for complex types
- Example:
  ```python
  def process_message(message: str, timeout: int = 30) -> Dict[str, Any]:
      """Process a message with optional timeout."""
      pass
  ```

#### Documentation
- Use docstrings for all public modules, classes, and functions
- Follow Google-style docstring format:
  ```python
  def fetch_data(url: str, retry_count: int = 3) -> Dict[str, Any]:
      """Fetch data from the specified URL.
      
      Args:
          url: The URL to fetch from.
          retry_count: Number of retries on failure (default: 3).
          
      Returns:
          A dictionary containing the fetched data.
          
      Raises:
          ValueError: If the URL is invalid.
          ConnectionError: If unable to connect after retries.
      """
  ```

### Running Tests

Before submitting a pull request, ensure all tests pass:

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run specific test file
poetry run pytest tests/test_memory.py

# Run with verbose output
poetry run pytest -v
```

**Test Requirements:**
- All new features must have corresponding tests
- Maintain or improve code coverage (currently targeting 80%+)
- Tests should be descriptive and isolated
- Use fixtures for common test setup

### Commit Messages

Follow the conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, missing semicolons, etc.)
- `refactor`: Code refactoring without feature changes
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `ci`: CI/CD changes
- `chore`: Other changes (dependencies, config, etc.)

**Examples:**
```
feat(memory): add neo4j backup functionality

Implement automated backup to iCloud with GFS retention policy.
Adds backup_status, backup_list, and backup_restore operations.

Closes #123
```

```
fix(event-bus): resolve message ordering race condition

Ensure messages are processed sequentially per topic using
a single consumer goroutine pattern.
```

## Submitting a Pull Request

### Before Submitting

1. **Update your branch** with latest upstream changes:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run full quality checks**:
   ```bash
   # Format code
   black src/ tests/
   isort src/ tests/
   
   # Run linter
   ruff check src/ tests/
   
   # Run tests
   poetry run pytest
   ```

3. **Push your branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

### PR Checklist

When creating a pull request, use the PR template and ensure:

- [ ] Description clearly explains the changes
- [ ] All tests pass locally
- [ ] Code follows style guidelines (black, isort, type hints)
- [ ] New features include tests
- [ ] Documentation is updated
- [ ] Commit messages follow conventional format
- [ ] No unrelated changes included
- [ ] No dependencies added without discussion

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Related Issues
Closes #<issue_number>

## Changes
- Specific change 1
- Specific change 2
- Specific change 3

## Testing
How to test these changes.

## Checklist
- [ ] Tests pass
- [ ] Code style checks pass
- [ ] Documentation updated
- [ ] No breaking changes
```

## Review Process

### What to Expect

1. **Automated checks**: GitHub Actions will automatically run tests and linting
2. **Code review**: Maintainers will review your code for:
   - Correctness and robustness
   - Code quality and style
   - Test coverage
   - Documentation completeness
3. **Feedback**: Reviewers may request changes or clarifications
4. **Approval**: Once approved by maintainers, the PR will be merged

### Addressing Feedback

- Respond to all comments
- Make requested changes on your branch
- Force push to update the PR (don't create new PRs)
- Re-request review after making changes

## Development Guidelines

### Architecture Considerations

- **Modularity**: Keep components loosely coupled
- **Testing**: Write testable code with dependency injection
- **Documentation**: Document non-obvious design decisions
- **Performance**: Profile before optimizing; add benchmarks for critical paths

### Adding Dependencies

- Keep dependencies minimal
- Prefer well-maintained, widely-used packages
- Discuss major dependency additions in an issue first
- Update `pyproject.toml` and documentation

### Breaking Changes

- Avoid breaking changes when possible
- If necessary, provide migration path
- Clearly document in commit message and PR description
- Consider deprecation period for major versions

## Questions or Need Help?

- Check existing [issues](https://github.com/josephmcateer/agentic-brain/issues) and [discussions](https://github.com/josephmcateer/agentic-brain/discussions)
- Read project documentation in `/docs`
- Create a new issue if you have questions
- Reach out to maintainers with concerns

## Recognition

Contributors will be recognized in:
- Project README
- Release notes for significant contributions
- GitHub Contributors page

Thank you for contributing to Agentic Brain!
