# PyPI Publishing Setup

This document explains how to set up automated PyPI publishing for the article-cli package.

## Option 1: Trusted Publishing (Recommended)

Trusted publishing is the most secure method and doesn't require managing API tokens.

### Setup Steps:

1. **Go to PyPI Project Settings**:
   - Visit: https://pypi.org/manage/project/article-cli/settings/publishing/
   - If the project doesn't exist yet, you'll need to upload the first version manually

2. **Add Trusted Publisher**:
   - Publisher: GitHub
   - Owner: `feelpp`
   - Repository name: `article.cli`
   - Workflow name: `publish.yml`
   - Environment name: `release` (optional)

3. **Create GitHub Environment** (if using environment protection):
   ```bash
   # Go to GitHub repository settings
   gh repo view feelpp/article.cli --web
   # Navigate to: Settings > Environments > New environment
   # Name: release
   # Add protection rules if desired
   ```

### Current Workflow

The main publishing workflow (`.github/workflows/publish.yml`) uses trusted publishing and will work automatically once PyPI is configured.

## Option 2: API Token (Fallback)

If trusted publishing isn't available, use API tokens.

### Setup Steps:

1. **Create PyPI API Token**:
   - Go to: https://pypi.org/manage/account/
   - Click "Add API token"
   - Name: `github-actions-article-cli`
   - Scope: "Entire account" (or project-specific after first upload)
   - Copy the token (starts with `pypi-`)

2. **Add GitHub Secret**:
   ```bash
   # Via GitHub UI:
   gh repo view feelpp/article.cli --web
   # Go to: Settings > Secrets and variables > Actions
   # Add secret: PYPI_API_TOKEN = your_pypi_token
   ```

3. **Switch to Token Workflow**:
   ```bash
   # Rename workflows to switch
   mv .github/workflows/publish.yml .github/workflows/publish-trusted.yml.disabled
   mv .github/workflows/publish-token.yml .github/workflows/publish.yml
   ```

## Manual First Upload

If automated publishing fails, you can upload the first version manually:

```bash
# Build the package
uv build

# Upload to PyPI (you'll be prompted for credentials)
uv run twine upload dist/*

# Or with token
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-your_token_here
uv run twine upload dist/*
```

## Testing the Upload

For testing, you can use TestPyPI:

```bash
# Upload to TestPyPI first
uv run twine upload --repository testpypi dist/*

# Install from TestPyPI to test
uv tool install --index-url https://test.pypi.org/simple/ article-cli
```

## Troubleshooting

### Common Issues:

1. **403 Forbidden**: Authentication issue
   - Check PyPI token is correct
   - Verify trusted publishing configuration
   - Ensure package name is available

2. **Package already exists**: Version conflict
   - Bump version in `pyproject.toml`
   - Create new release tag
   - PyPI doesn't allow overwriting existing versions

3. **Workflow doesn't trigger**: Release configuration
   - Ensure release is "published" not just "created"
   - Check workflow file syntax
   - Verify branch protection rules

### Debug Commands:

```bash
# Check current configuration
gh workflow list
gh run list --limit 5

# View workflow logs
gh run view [run-id] --log

# Test build locally
uv build
uv run twine check dist/*
```
