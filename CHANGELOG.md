# Changelog

All notable changes to the AgentSystems SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive test suite achieving 80% code coverage
- GitHub PR and issue templates for better collaboration
- Bug report, feature request, and documentation issue templates
- Test coverage for all CLI commands (clean, logs, restart, status, run, init, down)
- Improved test coverage for utility functions and progress tracker
- Dependency lock files for reproducible builds (`requirements-lock.txt`, `requirements-dev-lock.txt`)
- Automated dependency update workflow (weekly schedule via cron)
- Security scanning workflow with Bandit and Safety
- Workflow badges for CI, Security, and Dependencies

### Changed
- Enhanced test infrastructure with better mocking strategies
- Improved error handling test coverage
- CI/CD now uses lock files for reproducible builds
- Dependency updates handled automatically via GitHub Actions

### Fixed
- Various edge cases now covered by tests

## [0.1.0] - 2024-07-17

### Added
- Initial release of AgentSystems SDK
- CLI commands: init, up, down, logs, restart, status, run, clean, artifacts-path
- Docker and Docker Compose integration
- Langfuse observability support
- Agent configuration management
- Progress tracking for long-running operations
- Comprehensive CLI with both interactive and non-interactive modes
- Pre-commit hooks for code quality
- CI/CD pipeline with GitHub Actions
- Security policy and code of conduct
- Contribution guidelines

### Security
- Secure handling of Docker registry tokens
- Environment variable management for sensitive data

[Unreleased]: https://github.com/agentsystems/agentsystems-sdk/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/agentsystems/agentsystems-sdk/releases/tag/v0.1.0
