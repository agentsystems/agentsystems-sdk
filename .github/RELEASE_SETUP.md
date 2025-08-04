# Release Automation Setup

This document describes how to set up automated releases to PyPI for the AgentSystems SDK.

## Required Secrets

Configure these secrets in your GitHub repository settings under **Settings → Secrets and variables → Actions**:

### 1. `TEST_PYPI_TOKEN`
- **Purpose**: Authentication token for TestPyPI uploads
- **How to obtain**:
  1. Create account at https://test.pypi.org
  2. Go to https://test.pypi.org/manage/account/token/
  3. Create a new API token with scope "Entire account" or project-specific
  4. Copy the token (starts with `pypi-`)
  5. Add as repository secret

### 2. `PYPI_TOKEN`
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

### Manual Test (Workflow Dispatch)
1. Go to **Actions → Release to PyPI**
2. Click "Run workflow"
3. Enter version and select target (testpypi/pypi/both)
4. Monitor the workflow execution

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

- **Version validation**: Ensures git tag matches pyproject.toml version
- **Duplicate prevention**: Checks if version already exists on PyPI
- **Test stage**: Always publishes to TestPyPI first
- **Production approval**: Requires environment approval for PyPI
- **Artifact retention**: Keeps built distributions for 30 days
- **GitHub Release**: Automatically creates release with changelog
- **Installation verification**: Tests that package can be installed after upload

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
