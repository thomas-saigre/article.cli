"""
Subprocess execution boundary for article-cli services.
"""

import subprocess
from pathlib import Path
from typing import IO, Optional, Sequence, Union

Command = Sequence[Union[str, Path]]


class CommandRunner:
    """Thin wrapper around subprocess for service-level dependency injection."""

    def run(
        self,
        command: Command,
        cwd: Optional[Path] = None,
        capture_output: bool = True,
        text: bool = True,
        timeout: Optional[int] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run a command and return the completed process."""
        return subprocess.run(
            [str(part) for part in command],
            cwd=cwd,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            check=check,
        )

    def popen(
        self,
        command: Command,
        cwd: Optional[Path] = None,
        stdout: Optional[int] = subprocess.PIPE,
        stderr: Optional[int] = subprocess.STDOUT,
        universal_newlines: bool = True,
        bufsize: int = 1,
    ) -> subprocess.Popen:
        """Start a long-running command."""
        return subprocess.Popen(
            [str(part) for part in command],
            cwd=cwd,
            stdout=stdout,
            stderr=stderr,
            universal_newlines=universal_newlines,
            bufsize=bufsize,
        )

    def stream_lines(self, process: subprocess.Popen) -> None:
        """Stream process stdout line by line until it exits."""
        stream: Optional[IO[str]] = process.stdout
        if stream is None:
            return

        while True:
            output = stream.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                print(output.strip())


DEFAULT_RUNNER = CommandRunner()
