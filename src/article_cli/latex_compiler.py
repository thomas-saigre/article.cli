"""
LaTeX compilation module for article-cli

Provides compilation functionality that mimics LaTeX Workshop configuration
with support for latexmk and pdflatex engines.
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config
from .git_hooks import gitinfo2_metadata_summary, refresh_gitinfo2_metadata
from .zotero import print_error, print_info, print_success


class LaTeXCompiler:
    """Handles LaTeX document compilation with various engines and options"""

    def __init__(self, config: Config):
        """
        Initialize LaTeX compiler

        Args:
            config: Configuration instance
        """
        self.config = config
        self.latex_config = config.get_latex_config()
        self.timeout = int(self.latex_config.get("timeout", 300))

    def compile(
        self,
        tex_file: str,
        engine: str = "latexmk",
        shell_escape: bool = False,
        output_dir: Optional[str] = None,
        watch: bool = False,
    ) -> bool:
        """
        Compile LaTeX document

        Args:
            tex_file: Path to .tex file
            engine: Compilation engine ("latexmk" or "pdflatex")
            shell_escape: Enable shell escape
            output_dir: Output directory for compiled files
            watch: Watch for changes and recompile automatically

        Returns:
            True if compilation successful, False otherwise
        """
        tex_path = Path(tex_file)
        if not tex_path.exists():
            print_error(f"LaTeX file not found: {tex_file}")
            return False

        print_info(f"Compiling {tex_file} with {engine}...")
        if refresh_gitinfo2_metadata(tex_path.parent):
            print_info("Updated gitinfo2 metadata")
            summary = gitinfo2_metadata_summary(tex_path.parent)
            if summary:
                print_info(f"Version metadata: {summary}")

        if watch:
            return self._compile_watch(tex_path, engine, shell_escape, output_dir)
        else:
            return self._compile_once(tex_path, engine, shell_escape, output_dir)

    def _compile_once(
        self, tex_path: Path, engine: str, shell_escape: bool, output_dir: Optional[str]
    ) -> bool:
        """Compile document once"""
        if engine == "latexmk":
            return self._run_latexmk(tex_path, shell_escape, output_dir)
        elif engine == "pdflatex":
            return self._run_pdflatex(tex_path, shell_escape, output_dir)
        elif engine == "xelatex":
            return self._run_xelatex(tex_path, shell_escape, output_dir)
        elif engine == "lualatex":
            return self._run_lualatex(tex_path, shell_escape, output_dir)
        else:
            print_error(f"Unknown engine: {engine}")
            return False

    def _compile_watch(
        self, tex_path: Path, engine: str, shell_escape: bool, output_dir: Optional[str]
    ) -> bool:
        """Compile document and watch for changes"""
        if engine in ["pdflatex", "xelatex", "lualatex"]:
            print_error(
                "Watch mode is only supported with latexmk engine. "
                "Use: article-cli compile --engine latexmk --watch"
            )
            return False

        print_info("Starting watch mode. Press Ctrl+C to stop.")
        print_info("Watching for changes to .tex, .bib, .sty, .cls files...")

        try:
            # Use latexmk with preview continuous mode
            cmd = self._build_latexmk_command(
                tex_path, shell_escape, output_dir, continuous=True
            )

            process = subprocess.Popen(
                cmd,
                cwd=tex_path.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )

            # Stream output in real time
            try:
                while True:
                    if process.stdout is None:
                        break
                    output = process.stdout.readline()
                    if output == "" and process.poll() is not None:
                        break
                    if output:
                        print(output.strip())

            except KeyboardInterrupt:
                print_info("\nStopping watch mode...")
                process.terminate()
                process.wait()
                return True

            return process.returncode == 0

        except Exception as e:
            print_error(f"Watch mode failed: {e}")
            return False

    def _run_latexmk(
        self, tex_path: Path, shell_escape: bool, output_dir: Optional[str]
    ) -> bool:
        """Run latexmk compilation"""
        cmd = self._build_latexmk_command(tex_path, shell_escape, output_dir)

        try:
            print_info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=tex_path.parent,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0:
                pdf_name = tex_path.with_suffix(".pdf").name
                if output_dir:
                    pdf_path = Path(output_dir) / pdf_name
                else:
                    pdf_path = tex_path.with_suffix(".pdf")

                if pdf_path.exists():
                    print_success(f"✅ Compilation successful: {pdf_path}")
                    self._show_pdf_info(pdf_path)
                else:
                    print_error("Compilation reported success but PDF not found")
                    return False

                return True
            else:
                print_error("❌ Compilation failed")
                if result.stdout:
                    print("STDOUT:")
                    print(result.stdout)
                if result.stderr:
                    print("STDERR:")
                    print(result.stderr)
                return False

        except subprocess.TimeoutExpired:
            print_error(f"Compilation timed out after {self.timeout} seconds")
            return False
        except Exception as e:
            print_error(f"Compilation error: {e}")
            return False

    def _run_pdflatex(
        self, tex_path: Path, shell_escape: bool, output_dir: Optional[str]
    ) -> bool:
        """Run pdflatex compilation (multiple passes for cross-references)"""
        cmd = self._build_pdflatex_command(tex_path, shell_escape, output_dir)

        try:
            # Run multiple passes for cross-references, bibliography, etc.
            passes = ["First pass", "Second pass", "Third pass"]

            for i, pass_name in enumerate(passes):
                print_info(f"{pass_name}...")
                result = subprocess.run(
                    cmd,
                    cwd=tex_path.parent,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                if result.returncode != 0:
                    print_error(f"❌ {pass_name} failed")
                    if result.stdout:
                        print("STDOUT:")
                        print(result.stdout)
                    if result.stderr:
                        print("STDERR:")
                        print(result.stderr)
                    return False

                # Check if we need to run bibtex/biber
                if i == 0:  # After first pass
                    self._run_bibliography_if_needed(tex_path, result.stdout)

            pdf_name = tex_path.with_suffix(".pdf").name
            if output_dir:
                pdf_path = Path(output_dir) / pdf_name
            else:
                pdf_path = tex_path.with_suffix(".pdf")

            if pdf_path.exists():
                print_success(f"✅ Compilation successful: {pdf_path}")
                self._show_pdf_info(pdf_path)
                return True
            else:
                print_error("Compilation reported success but PDF not found")
                return False

        except subprocess.TimeoutExpired:
            print_error("Compilation timed out")
            return False
        except Exception as e:
            print_error(f"Compilation error: {e}")
            return False

    def _build_latexmk_command(
        self,
        tex_path: Path,
        shell_escape: bool,
        output_dir: Optional[str],
        continuous: bool = False,
        pdf_mode: str = "pdf",
    ) -> List[str]:
        """Build latexmk command based on LaTeX Workshop configuration

        Args:
            tex_path: Path to .tex file
            shell_escape: Enable shell escape
            output_dir: Output directory
            continuous: Enable preview continuous mode
            pdf_mode: PDF generation mode ("pdf", "xelatex", "lualatex")
        """
        cmd = ["latexmk"]

        # Core options (from LaTeX Workshop)
        if shell_escape:
            cmd.append("--shell-escape")

        # Select PDF generation engine
        if pdf_mode == "xelatex":
            cmd.append("-xelatex")
        elif pdf_mode == "lualatex":
            cmd.append("-lualatex")
        else:
            cmd.append("-pdf")  # Default: pdflatex

        cmd.extend(
            [
                "-interaction=nonstopmode",
                "-synctex=1",
            ]
        )

        if output_dir:
            cmd.extend(["-outdir", output_dir])

        if continuous:
            cmd.append("-pvc")  # Preview continuous mode

        cmd.append(str(tex_path))

        return cmd

    def _build_pdflatex_command(
        self, tex_path: Path, shell_escape: bool, output_dir: Optional[str]
    ) -> List[str]:
        """Build pdflatex command based on LaTeX Workshop configuration"""
        cmd = ["pdflatex"]

        # Core options (from LaTeX Workshop)
        if shell_escape:
            cmd.append("--shell-escape")

        cmd.extend(
            [
                "-synctex=1",
                "-interaction=nonstopmode",
                "-file-line-error",
            ]
        )

        if output_dir:
            cmd.extend(["-output-directory", output_dir])

        cmd.append(str(tex_path))

        return cmd

    def _run_xelatex(
        self, tex_path: Path, shell_escape: bool, output_dir: Optional[str]
    ) -> bool:
        """Run xelatex compilation (multiple passes for cross-references)"""
        cmd = self._build_xelatex_command(tex_path, shell_escape, output_dir)

        try:
            # Run multiple passes for cross-references, bibliography, etc.
            passes = ["First pass", "Second pass", "Third pass"]

            for i, pass_name in enumerate(passes):
                print_info(f"{pass_name} (xelatex)...")
                result = subprocess.run(
                    cmd,
                    cwd=tex_path.parent,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                if result.returncode != 0:
                    print_error(f"❌ {pass_name} failed")
                    if result.stdout:
                        print("STDOUT:")
                        print(result.stdout)
                    if result.stderr:
                        print("STDERR:")
                        print(result.stderr)
                    return False

                # Check if we need to run bibtex/biber
                if i == 0:  # After first pass
                    self._run_bibliography_if_needed(tex_path, result.stdout)

            pdf_name = tex_path.with_suffix(".pdf").name
            if output_dir:
                pdf_path = Path(output_dir) / pdf_name
            else:
                pdf_path = tex_path.with_suffix(".pdf")

            if pdf_path.exists():
                print_success(f"✅ Compilation successful: {pdf_path}")
                self._show_pdf_info(pdf_path)
                return True
            else:
                print_error("Compilation reported success but PDF not found")
                return False

        except subprocess.TimeoutExpired:
            print_error("Compilation timed out")
            return False
        except Exception as e:
            print_error(f"Compilation error: {e}")
            return False

    def _build_xelatex_command(
        self, tex_path: Path, shell_escape: bool, output_dir: Optional[str]
    ) -> List[str]:
        """Build xelatex command"""
        cmd = ["xelatex"]

        if shell_escape:
            cmd.append("--shell-escape")

        cmd.extend(
            [
                "-synctex=1",
                "-interaction=nonstopmode",
                "-file-line-error",
            ]
        )

        if output_dir:
            cmd.extend(["-output-directory", output_dir])

        cmd.append(str(tex_path))

        return cmd

    def _run_lualatex(
        self, tex_path: Path, shell_escape: bool, output_dir: Optional[str]
    ) -> bool:
        """Run lualatex compilation (multiple passes for cross-references)"""
        cmd = self._build_lualatex_command(tex_path, shell_escape, output_dir)

        try:
            # Run multiple passes for cross-references, bibliography, etc.
            passes = ["First pass", "Second pass", "Third pass"]

            for i, pass_name in enumerate(passes):
                print_info(f"{pass_name} (lualatex)...")
                result = subprocess.run(
                    cmd,
                    cwd=tex_path.parent,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                if result.returncode != 0:
                    print_error(f"❌ {pass_name} failed")
                    if result.stdout:
                        print("STDOUT:")
                        print(result.stdout)
                    if result.stderr:
                        print("STDERR:")
                        print(result.stderr)
                    return False

                # Check if we need to run bibtex/biber
                if i == 0:  # After first pass
                    self._run_bibliography_if_needed(tex_path, result.stdout)

            pdf_name = tex_path.with_suffix(".pdf").name
            if output_dir:
                pdf_path = Path(output_dir) / pdf_name
            else:
                pdf_path = tex_path.with_suffix(".pdf")

            if pdf_path.exists():
                print_success(f"✅ Compilation successful: {pdf_path}")
                self._show_pdf_info(pdf_path)
                return True
            else:
                print_error("Compilation reported success but PDF not found")
                return False

        except subprocess.TimeoutExpired:
            print_error("Compilation timed out")
            return False
        except Exception as e:
            print_error(f"Compilation error: {e}")
            return False

    def _build_lualatex_command(
        self, tex_path: Path, shell_escape: bool, output_dir: Optional[str]
    ) -> List[str]:
        """Build lualatex command"""
        cmd = ["lualatex"]

        if shell_escape:
            cmd.append("--shell-escape")

        cmd.extend(
            [
                "-synctex=1",
                "-interaction=nonstopmode",
                "-file-line-error",
            ]
        )

        if output_dir:
            cmd.extend(["-output-directory", output_dir])

        cmd.append(str(tex_path))

        return cmd

    def _run_bibliography_if_needed(self, tex_path: Path, latex_output: str) -> None:
        """Run bibtex or biber if needed based on latex output"""
        base_name = tex_path.stem

        # Check if bibliography is needed
        if (
            "citation undefined" in latex_output.lower()
            or "rerun" in latex_output.lower()
        ):
            # Check for .aux file to determine if we need bibtex
            aux_file = tex_path.with_suffix(".aux")
            if aux_file.exists():
                aux_content = aux_file.read_text()
                if "\\bibdata" in aux_content:
                    print_info("Running bibtex for bibliography...")
                    try:
                        subprocess.run(
                            ["bibtex", base_name],
                            cwd=tex_path.parent,
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                    except Exception as e:
                        print_info(f"Note: bibtex failed ({e}), continuing...")

    def _show_pdf_info(self, pdf_path: Path) -> None:
        """Show information about the generated PDF"""
        try:
            size = pdf_path.stat().st_size
            size_mb = size / (1024 * 1024)
            print_info(f"PDF size: {size_mb:.2f} MB")

            # Show modification time
            mtime = pdf_path.stat().st_mtime
            mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
            print_info(f"Generated: {mtime_str}")

        except Exception:
            pass  # Silently ignore errors getting file info

    def check_dependencies(self) -> Dict[str, bool]:
        """
        Check if required LaTeX tools are available

        Returns:
            Dictionary with tool availability status
        """
        tools = {
            "latexmk": self._check_command("latexmk"),
            "pdflatex": self._check_command("pdflatex"),
            "xelatex": self._check_command("xelatex"),
            "lualatex": self._check_command("lualatex"),
            "bibtex": self._check_command("bibtex"),
        }

        return tools

    def _check_command(self, command: str) -> bool:
        """Check if a command is available in PATH"""
        try:
            result = subprocess.run(
                [command, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def print_dependency_status(self) -> None:
        """Print status of LaTeX dependencies"""
        print_info("Checking LaTeX dependencies...")

        deps = self.check_dependencies()

        for tool, available in deps.items():
            status = "✅ Available" if available else "❌ Not found"
            print(f"  {tool}: {status}")

        if not all(deps.values()):
            print_info(
                "\nSome LaTeX tools are missing. Install a LaTeX distribution like TeX Live."
            )
            print_info("On macOS: brew install --cask mactex")
            print_info("On Ubuntu: sudo apt-get install texlive-full")
