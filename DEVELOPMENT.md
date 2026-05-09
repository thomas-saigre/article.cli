# Article CLI Development Setup

This guide helps you set up the article-cli package for development and distribution.

## Development Setup

1. **Create the package structure** (already done):
   ```
   article-cli-package/
   ├── pyproject.toml
   ├── README.md
   ├── LICENSE
   ├── src/
   │   └── article_cli/
   │       ├── __init__.py
   │       ├── cli.py
   │       ├── config.py
   │       ├── zotero.py
   │       └── git_manager.py
   └── tests/
       ├── __init__.py
       └── test_config.py
   ```

2. **Install development dependencies with uv**:
   ```bash
   cd article-cli-package
   uv sync --all-extras --dev
   ```

3. **Run checks through uv**:
   ```bash
   uv run pytest
   uv run black --check src tests
   uv run mypy src
   ```

## Building and Publishing

### Build the Package

```bash
# Build the package
uv build
```

This creates `dist/` directory with:
- `article_cli-1.0.0-py3-none-any.whl` (wheel)
- `article_cli-1.0.0.tar.gz` (source distribution)

### Test the Package Locally

```bash
# Install the local wheel into uv's tool environment
uv tool install dist/article_cli-1.0.0-py3-none-any.whl --force

# Test the CLI
article-cli --help
```

### Publish to PyPI

1. **Test upload to TestPyPI first**:
   ```bash
   # Register at https://test.pypi.org/ first
   uv run twine upload --repository testpypi dist/*
   ```

2. **Install from TestPyPI to verify**:
   ```bash
   uv tool install --index-url https://test.pypi.org/simple/ article-cli
   ```

3. **Upload to real PyPI**:
   ```bash
   # Register at https://pypi.org/ first
   uv run twine upload dist/*
   ```

## Migration Strategy

### Phase 1: Package Creation ✅
- [x] Create PyPI package structure
- [x] Port existing `a.py` functionality
- [x] Add configuration file support
- [x] Create comprehensive documentation

### Phase 2: Repository Updates

1. **Update article.template**:
   ```bash
   cd ../article.template
   
   # Remove old a.cli
   rm a.cli
   
   # Create or update pyproject.toml with article-cli as a dependency
   uv add article-cli
   
   # Update setup instructions in README
   ```

2. **Create installation script** (`setup.sh` in article.template):
   ```bash
   #!/bin/bash
   echo "Setting up article repository..."
   
   # Run article-cli from uv
   uvx article-cli setup
   
   # Create local config if it doesn't exist
   if [ ! -f .article-cli.toml ]; then
       uvx article-cli config create
       echo "Please edit .article-cli.toml with your Zotero credentials"
   fi
   
   echo "Setup complete!"
   ```

### Phase 3: Existing Repositories

For each existing article repository:

1. **Remove old files**:
   ```bash
   rm a.py a.cli  # Remove old scripts
   ```

2. **Install the package**:
   ```bash
   uv tool install article-cli
   ```

3. **Create local configuration**:
   ```bash
   article-cli config create
   # Edit .article-cli.toml with your settings
   ```

4. **Update any scripts/Makefiles** that reference `python a.py` to use `article-cli`

## Configuration Examples

### Example `.article-cli.toml`

```toml
[zotero]
api_key = "your_zotero_api_key_here"
group_id = "4678293"  # Default for article.template, or use user_id instead
output_file = "references.bib"

[git]
auto_push = false  # Set to true for automatic pushing
default_branch = "main"

[latex]
clean_extensions = [
    ".aux", ".bbl", ".blg", ".log", ".out", ".synctex.gz",
    ".toc", ".fdb_latexmk", ".idx", ".ilg", ".ind"
]
```

### Global Configuration

You can also create a global config at `~/.article-cli.toml`:

```toml
[zotero]
api_key = "your_api_key"
# Don't put group_id here - this varies per project

[git]
auto_push = true
```

## Command Comparison

| Old Command | New Command |
|-------------|-------------|
| `python a.py setup` | `article-cli setup` |
| `python a.py clean` | `article-cli clean` |
| `python a.py create v1.0.0` | `article-cli create v1.0.0` |
| `python a.py list` | `article-cli list` |
| `python a.py delete v1.0.0` | `article-cli delete v1.0.0` |
| `python a.py update-bibtex` | `article-cli update-bibtex` |

## Benefits of This Approach

1. **Centralized Maintenance**: Update once, benefit everywhere
2. **Easy Installation**: `uv tool install article-cli`
3. **Configuration Management**: Project-specific and global settings
4. **Better Error Handling**: Improved user experience
5. **Documentation**: Comprehensive help and examples
6. **Testing**: Proper test suite for reliability
7. **Versioning**: Semantic versioning for compatibility

## Testing

```bash
# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=article_cli

# Lint code
uv run flake8 src/
uv run black src tests
uv run mypy src/
```

## Continuous Updates

When you need to update the tool:

1. Make changes to the source code
2. Update version in `pyproject.toml`
3. Build and publish new version
4. Users update with: `uv tool upgrade article-cli`
