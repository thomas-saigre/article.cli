"""
Typst compilation module for article-cli

Provides compilation functionality for Typst documents with support for
watch mode and custom font paths.
"""

import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config
from .reporting import print_error, print_info, print_success


class TypstCompiler:
    """Handles Typst document compilation with various options"""

    def __init__(self, config: Config):
        """
        Initialize Typst compiler

        Args:
            config: Configuration instance
        """
        self.config = config
        self.typst_config = config.get_typst_config()

    def compile(
        self,
        typ_file: str,
        output_dir: Optional[str] = None,
        font_paths: Optional[List[str]] = None,
        watch: bool = False,
    ) -> bool:
        """
        Compile Typst document

        Args:
            typ_file: Path to .typ file
            output_dir: Output directory for compiled files
            font_paths: List of font directories to search
            watch: Watch for changes and recompile automatically

        Returns:
            True if compilation successful, False otherwise
        """
        typ_path = Path(typ_file)
        if not typ_path.exists():
            print_error(f"Typst file not found: {typ_file}")
            return False

        print_info(f"Compiling {typ_file} with Typst...")

        # Merge font paths from config and arguments
        all_font_paths = list(self.typst_config.get("font_paths", []))
        if font_paths:
            all_font_paths.extend(font_paths)

        if watch:
            return self._compile_watch(typ_path, output_dir, all_font_paths)
        else:
            return self._compile_once(typ_path, output_dir, all_font_paths)

    def _compile_once(
        self,
        typ_path: Path,
        output_dir: Optional[str],
        font_paths: List[str],
    ) -> bool:
        """Compile document once"""
        cmd = self._build_compile_command(typ_path, output_dir, font_paths)

        try:
            print_info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=typ_path.parent,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
            )

            if result.returncode == 0:
                pdf_name = typ_path.with_suffix(".pdf").name
                if output_dir:
                    pdf_path = Path(output_dir) / pdf_name
                else:
                    pdf_path = typ_path.with_suffix(".pdf")

                if pdf_path.exists():
                    print_success(f"✅ Compilation successful: {pdf_path}")
                    self._show_pdf_info(pdf_path)
                    self._show_pdf_page_count(pdf_path)
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
            print_error("Compilation timed out after 2 minutes")
            return False
        except FileNotFoundError:
            print_error(
                "Typst not found. Install it with: brew install typst (macOS) "
                "or cargo install typst-cli"
            )
            return False
        except Exception as e:
            print_error(f"Compilation error: {e}")
            return False

    def _compile_watch(
        self,
        typ_path: Path,
        output_dir: Optional[str],
        font_paths: List[str],
    ) -> bool:
        """Compile document and watch for changes"""
        print_info("Starting watch mode. Press Ctrl+C to stop.")
        print_info("Watching for changes to .typ files...")

        try:
            cmd = self._build_watch_command(typ_path, output_dir, font_paths)

            process = subprocess.Popen(
                cmd,
                cwd=typ_path.parent,
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

        except FileNotFoundError:
            print_error(
                "Typst not found. Install it with: brew install typst (macOS) "
                "or cargo install typst-cli"
            )
            return False
        except Exception as e:
            print_error(f"Watch mode failed: {e}")
            return False

    def _build_compile_command(
        self,
        typ_path: Path,
        output_dir: Optional[str],
        font_paths: List[str],
    ) -> List[str]:
        """Build typst compile command

        Args:
            typ_path: Path to .typ file
            output_dir: Output directory
            font_paths: List of font directories
        """
        cmd = ["typst", "compile"]

        # Add font paths
        for font_path in font_paths:
            cmd.extend(["--font-path", font_path])

        # Add input file
        cmd.append(str(typ_path))

        # Add output file if output_dir specified
        if output_dir:
            output_path = Path(output_dir) / typ_path.with_suffix(".pdf").name
            cmd.append(str(output_path))

        return cmd

    def _build_watch_command(
        self,
        typ_path: Path,
        output_dir: Optional[str],
        font_paths: List[str],
    ) -> List[str]:
        """Build typst watch command

        Args:
            typ_path: Path to .typ file
            output_dir: Output directory
            font_paths: List of font directories
        """
        cmd = ["typst", "watch"]

        # Add font paths
        for font_path in font_paths:
            cmd.extend(["--font-path", font_path])

        # Add input file
        cmd.append(str(typ_path))

        # Add output file if output_dir specified
        if output_dir:
            output_path = Path(output_dir) / typ_path.with_suffix(".pdf").name
            cmd.append(str(output_path))

        return cmd

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

    def _show_pdf_page_count(self, pdf_path: Path) -> None:
        """Print PDF page count when pdfinfo is available."""
        if shutil.which("pdfinfo") is None:
            return
        try:
            result = subprocess.run(
                ["pdfinfo", str(pdf_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception:
            return
        if result.returncode != 0:
            return
        match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.MULTILINE)
        if match:
            print_info(f"PDF pages: {match.group(1)}")

    def check_dependencies(self) -> Dict[str, bool]:
        """
        Check if Typst is available

        Returns:
            Dictionary with tool availability status
        """
        tools = {
            "typst": self._check_command("typst"),
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
        """Print status of Typst dependencies"""
        print_info("Checking Typst dependencies...")

        deps = self.check_dependencies()

        for tool, available in deps.items():
            status = "✅ Available" if available else "❌ Not found"
            print(f"  {tool}: {status}")

        if not all(deps.values()):
            print_info("\nTypst is not installed. Install it with:")
            print_info("  macOS: brew install typst")
            print_info("  Cargo: cargo install typst-cli")
            print_info("  Or download from: https://github.com/typst/typst/releases")
