# Release Automation Setup

This document describes how to set up automated releases to PyPI for the AgentSystems SDK.

## Required Secrets

Configure these secrets in your GitHub repository settings under **Settings → Secrets and variables → Actions**:

### 1. `TEST_PYPI_API_TOKEN`
- **Purpose**: Authentication token for TestPyPI uploads
- **How to obtain**:
  1. Create account at https://test.pypi.org
  2. Go to https://test.pypi.org/manage/account/token/
  3. Create a new API token with scope "Entire account" or project-specific
  4. Copy the token (starts with `pypi-`)
  5. Add as repository secret

### 2. `PYPI_API_TOKEN`
- **Purpose**: Authentication token for production PyPI uploads
- **How to obtain**:
  1. Create account at https://pypi.org
  2. Go to https://pypi.org/manage/account/token/
  3. Create a new API token with scope "Entire account" or project-specific
  4. Copy the token (starts with `pypi-`)
  5. Add as repository secret

## Environment Protection

The workflow uses GitHub Environments for additional protection:

### `testpypi` Environment
- **Purpose**: Controls TestPyPI releases
- **Setup**:
  - Go to **Settings → Environments**
  - Create `testpypi` environment
  - Optional: Add reviewers or deployment protection rules

### `pypi` Environment
- **Purpose**: Controls production PyPI releases
- **Setup**:
  - Go to **Settings → Environments**
  - Create `pypi` environment
  - **Recommended**: Add required reviewers for production releases
  - **Recommended**: Restrict to protected branches only

## Testing the Workflow

### Manual Release (Workflow Dispatch)

The workflow uses a two-step release process for safety:

1. Go to **Actions → Release to PyPI**
2. Click "Run workflow"
3. Select options:
   - **Branch**: Your release branch (e.g., `release/0.2.27`)
   - **Release target**:
     - `testpypi` - Release to TestPyPI only (for testing)
     - `pypi` - Release to production PyPI only (after TestPyPI validation)
   - **Dry run**:
     - `true` - Build only, no upload
     - `false` - Build and upload
4. Monitor the workflow execution

**Important**: There is no "both" option. You must:
1. First run with `target: testpypi` to validate
2. Then run with `target: pypi` after testing

## Recommended Release Process

1. **Create release branch**:
   ```bash
   git checkout -b release/X.Y.Z
   # Update version in pyproject.toml
   git commit -am "chore: bump version to X.Y.Z"
   git push -u origin release/X.Y.Z
   ```

2. **Create PR** (but don't merge yet)

3. **Release to TestPyPI**:
   - Run workflow from release branch
   - Target: `testpypi`
   - Test the package thoroughly

4. **If TestPyPI passes**:
   - Merge PR to main
   - Run workflow again with target: `pypi`

5. **If TestPyPI fails**:
   - Fix issues on release branch
   - Re-run TestPyPI release
   - Only merge after success

### Automated Test (Tag Push)
1. Create a release branch:
   ```bash
   git checkout -b release/x.y.z
   vim pyproject.toml  # Update version
   git commit -am "chore: bump version to x.y.z"
   ```

2. Push tag to trigger workflow:
   ```bash
   git tag -a vx.y.z -m "Release vx.y.z"
   git push origin vx.y.z
   ```

## Workflow Features

- **Two-step release process**: Separate TestPyPI and PyPI releases for safety
- **Version validation**: Ensures consistency across pyproject.toml
- **Duplicate prevention**: Checks if version already exists on target index
- **Installation verification**:
  - TestPyPI: Retry logic for propagation delays, comprehensive CLI tests
  - PyPI: Basic smoke test after upload
- **Production approval**: Optional environment protection for PyPI
- **Artifact retention**: Keeps built distributions for 7 days
- **GitHub Release**: Automatically creates release with tag `vX.Y.Z`
- **Automatic testing**: Verifies `--version` and `--help` commands work

## Troubleshooting

### "Version already exists" Error
- Each version can only be uploaded once to PyPI
- Increment version in pyproject.toml and create new tag

### Authentication Failures
- Verify tokens are correctly set in repository secrets
- Ensure tokens have correct scope (project or entire account)
- Check token hasn't expired

### Environment Protection Blocking
- Check environment protection rules in repository settings
- Ensure you have required approvals if configured

## Rollback Procedure

If a bad release is published:

1. **Yank the release on PyPI** (doesn't delete, but prevents new installs):
   ```bash
   pip install twine
   twine yank agentsystems-sdk==x.y.z
   ```

2. **Create a patch release** with the fix:
   ```bash
   git checkout -b release/x.y.z+1
   # Fix the issue
   vim pyproject.toml  # Bump to x.y.z+1
   git commit -am "fix: patch for x.y.z issue"
   git tag -a vx.y.z+1 -m "Patch release vx.y.z+1"
   git push origin vx.y.z+1
   ```

## Security Notes

- Never commit PyPI tokens to the repository
- Use environment protection for production releases
- Rotate tokens periodically
- Use project-scoped tokens when possible (more secure than account-wide)
