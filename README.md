# Article CLI

[![CI](https://github.com/feelpp/article.cli/actions/workflows/ci.yml/badge.svg)](https://github.com/feelpp/article.cli/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/article-cli.svg)](https://badge.fury.io/py/article-cli)
[![Python Support](https://img.shields.io/pypi/pyversions/article-cli.svg)](https://pypi.org/project/article-cli/)

A command-line tool for managing LaTeX and Typst documents with git integration and Zotero bibliography synchronization.

## Features

- **Repository Initialization**: Complete setup for LaTeX or Typst projects with one command
- **Project Types**: Support for articles, Beamer presentations, posters, and Typst documents
- **LaTeX Compilation**: Compile documents with latexmk/pdflatex/xelatex/lualatex, watch mode, shell escape support
- **Typst Compilation**: Full support for Typst documents with watch mode and custom font paths
- **Font Installation**: Download and install fonts for XeLaTeX projects (Marianne, Roboto Mono, etc.)
- **GitHub Actions Workflows**: Automated PDF compilation with XeLaTeX support, artifact upload, and GitHub releases
- **Git Release Management**: Create, list, and delete releases with gitinfo2 support
- **Zotero Integration**: Synchronize bibliography from Zotero with robust pagination and error handling
- **Lifecycle Commands**: Use `init`, `setup`, `doctor`, `bib update`, `compile`, `version`, and `release`
- **LaTeX Build Management**: Clean build files and manage LaTeX compilation artifacts
- **Git Hooks Setup**: Automated setup of git hooks for gitinfo2 integration
- **Repository Diagnostics**: Read-only `doctor` checks for git, hooks, build tools, Zotero, workflows, and release readiness
- **Project Configuration**: Auto-generates pyproject.toml with article-cli settings
- **Documentation**: Creates README with build instructions and usage guide

## Installation

### From PyPI (recommended)

```bash
uv tool install article-cli
```

### From Source

```bash
git clone https://github.com/feelpp/article.cli.git
cd article.cli
uv sync --all-extras --dev
uv run article-cli --help
```

### Development Commands

```bash
uv sync --all-extras --dev
uv run pytest
uv run black --check src tests
uv run mypy src
uv build
```

## Quick Start

### For New Projects

1. **Initialize your LaTeX article repository**:
   ```bash
   cd your-article-repo
   article-cli init --title "Your Article Title" --authors "Author One,Author Two"
   ```

   This creates:
   - `.github/workflows/latex.yml` - Complete CI/CD pipeline
   - `pyproject.toml` - Project configuration with article-cli settings
   - `README.md` - Documentation and usage instructions
   - `.gitignore` - LaTeX-specific ignore rules
   - `.vscode/settings.json` - LaTeX Workshop configuration
   - `.vscode/ltex.dictionary.en-US.txt` - Custom dictionary

2. **Configure Zotero** (add as GitHub secret):
   ```bash
   export ZOTERO_API_KEY="your_api_key_here"
   ```

3. **Setup git hooks and update bibliography**:
   ```bash
   article-cli doctor
   article-cli setup --dry-run
   article-cli setup
   article-cli bib update --dry-run
   article-cli bib update
   ```

4. **Commit and push** to trigger automated PDF compilation!

### For Existing Projects

1. **Setup git hooks** (run once per repository):
   ```bash
   article-cli doctor
   article-cli setup
   ```

2. **Configure Zotero credentials**:
   ```bash
   export ZOTERO_API_KEY="your_api_key_here"
   export ZOTERO_GROUP_ID="your_group_id"  # or ZOTERO_USER_ID
   ```

3. **Update bibliography from Zotero**:
   ```bash
   article-cli bib update
   ```

4. **Compile, refresh version metadata, and create a release**:
   ```bash
   article-cli compile
   article-cli version
   article-cli release v1.0.0 --dry-run
   article-cli release v1.0.0
   ```

## Configuration

### Environment Variables

- `ZOTERO_API_KEY`: Your Zotero API key (required for bibliography updates)
- `ZOTERO_USER_ID`: Your Zotero user ID (alternative to group ID)
- `ZOTERO_GROUP_ID`: Your Zotero group ID (alternative to user ID)

### Local Configuration File

Create a `.article-cli.toml` file in your project root for project-specific settings:

```toml
[zotero]
api_key = "your_api_key_here"
group_id = "4678293"  # Default for article.template
# user_id = "your_user_id"  # alternative to group_id
output_file = "references.bib"

[git]
auto_push = false
default_branch = "main"

[workflow]
runner_policy = "github"
github_runner = "ubuntu-24.04"
self_hosted_label = "self-texlive"
self_hosted_org = ""
bibliography = "off"
release = "github"
artifact_includes = []

[latex]
clean_extensions = [".aux", ".bbl", ".blg", ".log", ".out", ".synctex.gz"]

[fonts]
directory = "fonts"

[fonts.sources]
marianne = "https://github.com/ArnaudBelcworking/Marianne/archive/refs/heads/master.zip"
roboto-mono = "https://github.com/googlefonts/RobotoMono/releases/download/v3.000/RobotoMono-v3.000.zip"

[themes]
directory = "."

# Custom theme sources (numpex is built-in)
# [themes.sources.my-theme]
# url = "https://example.com/theme.zip"
# description = "My custom theme"
# files = ["beamerthememytheme.sty"]
# typst_files = ["mytheme.typ"]
# requires_fonts = false
# engine = "pdflatex"

[typst]
font_paths = ["fonts/", "~/.fonts/"]
build_dir = "build"
```

## Usage

### Repository Initialization

```bash
# Initialize a new article repository (auto-detects main .tex file)
article-cli init --title "My Article Title" --authors "John Doe,Jane Smith"

# Initialize a Beamer presentation project
article-cli init --title "My Presentation" --authors "Author" --type presentation

# Initialize with numpex theme (requires theme files from presentation.template.d)
article-cli init --title "NumPEx Talk" --authors "Author" --type presentation --theme numpex

# Initialize a Typst presentation project
article-cli init --title "My Typst Talk" --authors "Author" --type typst-presentation

# Initialize a Typst poster project
article-cli init --title "My Typst Poster" --authors "Author" --type typst-poster

# Specify custom Zotero group ID
article-cli init --title "My Article" --authors "Author" --group-id 1234567

# Specify main .tex file explicitly
article-cli init --title "My Article" --authors "Author" --tex-file article.tex

# Force overwrite existing files
article-cli init --title "My Article" --authors "Author" --force

# Generate CI that checks Zotero bibliography freshness
article-cli init --title "My Article" --authors "Author" --ci-bib check

# Generate CI with opt-in self-hosted runner discovery
article-cli init --title "My Article" --authors "Author" \
  --ci-runner-policy self-hosted-auto --ci-self-hosted-org my-org
```

The `init` command sets up:
- **GitHub Actions workflow** for automated PDF compilation and releases (with XeLaTeX support for presentations)
- **pyproject.toml** with dependencies and article-cli configuration
- **README.md** with comprehensive documentation
- **.gitignore** with LaTeX-specific patterns
- **VS Code configuration** for LaTeX Workshop with auto-build and SyncTeX
- **Font configuration** (for presentation projects using custom themes)

### Git Release Management

```bash
# Refresh gitinfo2 version metadata
article-cli version

# Refresh metadata, compile, and check the PDF version text
article-cli version --compile --check-pdf

# Preview a new release tag
article-cli release v1 --dry-run

# Create a checked local release tag
article-cli release v1

# Check bibliography freshness during release, then push the tag
article-cli release v1 --bib check --push

# List recent releases
article-cli list --count 10

# Delete a release
article-cli delete v1.2.3

# Deprecated alias retained for compatibility
article-cli create v1.2.3
```

### Bibliography Management

```bash
# Preview bibliography update
article-cli bib update --dry-run

# Update bibliography from Zotero
article-cli bib update

# Specify custom output file
article-cli bib update --output my-refs.bib

# Skip backup creation
article-cli bib update --no-backup

# Deprecated alias retained for compatibility
article-cli update-bibtex
```

### LaTeX Compilation

```bash
# Compile with latexmk (default engine)
article-cli compile

# Compile specific file with latexmk
article-cli compile main.tex

# Compile with pdflatex engine
article-cli compile --engine pdflatex

# Compile with XeLaTeX (for custom fonts)
article-cli compile --engine xelatex

# Compile with LuaLaTeX
article-cli compile --engine lualatex

# Enable shell escape (for code highlighting, etc.)
article-cli compile --shell-escape

# Watch for changes and auto-recompile
article-cli compile --watch

# Clean before and after compilation
article-cli compile --clean-first --clean-after

# Specify output directory
article-cli compile --output-dir build/
```

### Typst Compilation

```bash
# Compile a Typst document (auto-detects .typ files)
article-cli compile presentation.typ

# Compile with explicit Typst engine
article-cli compile --engine typst document.typ

# Watch for changes and auto-recompile
article-cli compile presentation.typ --watch

# Specify custom font paths
article-cli compile presentation.typ --font-path fonts/

# Multiple font paths
article-cli compile presentation.typ --font-path fonts/ --font-path ~/.fonts/

# Specify output directory
article-cli compile presentation.typ --output-dir build/
```

**Note:** The engine is automatically detected from the file extension:
- `.tex` files use LaTeX engines (latexmk by default)
- `.typ` files use the Typst engine

### Font Installation

Install fonts for XeLaTeX projects (useful for custom Beamer themes):

```bash
# Install default fonts (Marianne, Roboto Mono) to fonts/ directory
article-cli install-fonts

# Install to a custom directory
article-cli install-fonts --dir custom-fonts/

# Force re-download even if fonts exist
article-cli install-fonts --force

# List installed fonts
article-cli install-fonts --list
```

**Default fonts:**
- **Marianne**: French government official font
- **Roboto Mono**: Google's monospace font for code

### Theme Installation

Install Beamer themes for presentations:

```bash
# List available themes
article-cli install-theme --list

# Install numpex theme (NumPEx Beamer theme)
article-cli install-theme numpex

# Install to a custom directory
article-cli install-theme numpex --dir themes/

# Force re-download even if theme exists
article-cli install-theme numpex --force

# Install from a custom URL
article-cli install-theme my-theme --url https://example.com/theme.zip
```

**Available themes:**
- **numpex**: NumPEx theme following French government visual identity
  - LaTeX: Beamer theme files (requires XeLaTeX and custom fonts)
  - Typst: `numpex.typ` theme file for Typst presentations

**Complete LaTeX presentation setup:**
```bash
# 1. Install the theme
article-cli install-theme numpex

# 2. Install required fonts
article-cli install-fonts

# 3. Compile with XeLaTeX
article-cli compile presentation.tex --engine xelatex
```

**Complete Typst presentation setup:**
```bash
# 1. Install the theme (includes numpex.typ)
article-cli install-theme numpex

# 2. Compile with Typst
article-cli compile presentation.typ --font-path fonts/
```

### Project Setup

```bash
# Diagnose repository readiness without modifying files
article-cli doctor

# Emit machine-readable diagnostics for CI
article-cli doctor --json

# Setup git hooks for gitinfo2
article-cli setup

# Clean LaTeX build files
article-cli clean
```

### Advanced Usage

```bash
# Override configuration via command line
article-cli bib update --api-key YOUR_KEY --group-id YOUR_GROUP

# Specify custom configuration file
article-cli --config custom-config.toml bib update
```

## Release Tags

The default paper release policy accepts short and full version tags:
- `vX` for paper milestones (e.g., `v1`)
- `vX.Y` or `vX.Y.Z` for more detailed paper releases
- `vX.Y.Z-rc.N`, `vX.Y.Z-beta.N`, or similar pre-release suffixes

Use `[tool.article-cli.release] tag_policy = "semver"` when a repository must require strict `vX.Y.Z` semantic-version tags. The release command does not commit, force-retag, push, or create a GitHub release unless the corresponding explicit flag is passed.

## Requirements

- Python 3.9+
- Git repository with gitinfo2 package (for LaTeX integration)
- Zotero account with API access (for bibliography features)
- Typst CLI (for Typst compilation) - install from https://typst.app/

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Changelog

### v1.5.0
- Add read-only `doctor` diagnostics with JSON output
- Split CLI implementation into command modules
- Make setup hooks more robust and worktree-safe
- Standardize development and CI workflows on `uv`

### v1.4.0
- Add full Typst document compilation support
- New `TypstCompiler` class for Typst documents
- Auto-detection of `.typ` files with automatic engine selection
- Watch mode for Typst with live recompilation
- Custom font path support (`--font-path` option)
- New project types: `typst-presentation` and `typst-poster`
- Theme installation now includes Typst files (e.g., `numpex.typ`)
- Typst configuration section in config files

### v1.3.0
- Add theme installation command (`install-theme`) for Beamer presentations
- Built-in support for numpex theme with automatic download
- Extended GitHub Actions workflow with XeLaTeX and multi-document support

### v1.2.0
- Add font installation command (`install-fonts`) for XeLaTeX projects
- Support Marianne and Roboto Mono fonts by default
- Add presentation project type with Beamer template support
- Add `--engine` option for xelatex and lualatex compilation
- Improved CI/CD with font installation steps

### v1.1.0
- Add `init` command for repository initialization
- Add `compile` command with watch mode and multiple engines
- GitHub Actions workflow generation
- VS Code configuration generation

### v1.0.0
- Initial release
- Git release management
- Zotero bibliography synchronization
- LaTeX build file cleanup
- Configuration file support
