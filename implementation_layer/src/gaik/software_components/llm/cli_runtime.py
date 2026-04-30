"""Safe CLI-runtime registry for future local model adapters.

This module does not assume any specific CLI is installed. It provides:

- a typed registry of supported local CLI targets
- safe argv construction without shell interpolation
- an invocation surface that can be wired behind ProviderClient adapters later
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Literal

CliProviderKey = Literal[
    "claude_code_cli",
    "codex_cli",
    "gemini_cli",
    "github_copilot_cli",
    "snowflake_cortex_cli",
]


@dataclass(frozen=True)
class CliModelTarget:
    """Definition of one supported local CLI surface."""

    provider_key: CliProviderKey
    executable: tuple[str, ...]
    intended_models: tuple[str, ...]
    target_factory_surface: str
    structured_output_supported: bool = False
    implementation_note: str = ""

    @property
    def display_command(self) -> str:
        return " ".join(self.executable)


@dataclass(frozen=True)
class CliInvocationRequest:
    """Normalized local-model invocation request."""

    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    timeout_s: int = 120
    extra_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class CliInvocationResult:
    """Subprocess result from a local CLI invocation."""

    provider_key: CliProviderKey
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str


def get_default_cli_runtime_targets() -> tuple[CliModelTarget, ...]:
    """Return the built-in CLI registry used by higher-level workflows."""

    return (
        CliModelTarget(
            provider_key="claude_code_cli",
            executable=("claude",),
            intended_models=("Claude Code subscription models",),
            target_factory_surface="gaik.software_components.llm.ProviderClient",
            implementation_note=(
                "Wrap the Claude CLI behind a ProviderClient adapter once a stable "
                "non-interactive structured-output command is available."
            ),
        ),
        CliModelTarget(
            provider_key="codex_cli",
            executable=("codex",),
            intended_models=("Codex / ChatGPT subscription models",),
            target_factory_surface="gaik.software_components.llm.ProviderClient",
            implementation_note=(
                "Use subprocess argv lists only; never shell-expand user prompts."
            ),
        ),
        CliModelTarget(
            provider_key="gemini_cli",
            executable=("gemini",),
            intended_models=("Gemini subscription models",),
            target_factory_surface="gaik.software_components.llm.ProviderClient",
            implementation_note=(
                "Use this local target only when API-backed Google/Vertex access is not desired."
            ),
        ),
        CliModelTarget(
            provider_key="github_copilot_cli",
            executable=("gh", "copilot"),
            intended_models=("GitHub Copilot subscription models",),
            target_factory_surface="gaik.software_components.llm.ProviderClient",
            implementation_note=(
                "Restrict usage to supported non-interactive invocations that can be parsed "
                "deterministically."
            ),
        ),
        CliModelTarget(
            provider_key="snowflake_cortex_cli",
            executable=("snow", "sql"),
            intended_models=("Snowflake Cortex models",),
            target_factory_surface="gaik.software_components.llm.ProviderClient",
            implementation_note=(
                "Route through a configured warehouse and normalize results to ProviderClient."
            ),
        ),
    )


class CliModelRuntime:
    """Registry + safe subprocess invoker for local model CLIs."""

    def __init__(self, targets: tuple[CliModelTarget, ...] | None = None) -> None:
        self._targets = {
            target.provider_key: target
            for target in (targets or get_default_cli_runtime_targets())
        }

    def list_targets(self) -> tuple[CliModelTarget, ...]:
        return tuple(self._targets.values())

    def get_target(self, provider_key: CliProviderKey) -> CliModelTarget:
        try:
            return self._targets[provider_key]
        except KeyError as exc:
            raise ValueError(f"Unknown CLI runtime target: {provider_key}") from exc

    def is_available(self, provider_key: CliProviderKey) -> bool:
        target = self.get_target(provider_key)
        return shutil.which(target.executable[0]) is not None

    def build_command(
        self,
        provider_key: CliProviderKey,
        request: CliInvocationRequest,
    ) -> tuple[str, ...]:
        """Build a shell-free argv tuple for safe subprocess execution."""

        target = self.get_target(provider_key)
        argv = list(target.executable)
        if request.model:
            argv.extend(("--model", request.model))
        if request.system_prompt:
            argv.extend(("--system", request.system_prompt))
        argv.extend(request.extra_args)
        argv.extend(("--prompt", request.prompt))
        return tuple(argv)

    def invoke(
        self,
        provider_key: CliProviderKey,
        request: CliInvocationRequest,
    ) -> CliInvocationResult:
        """Invoke a local CLI without shell interpolation."""

        if not self.is_available(provider_key):
            target = self.get_target(provider_key)
            raise FileNotFoundError(
                f"CLI target '{provider_key}' is not installed or not on PATH "
                f"(expected command: {target.display_command})"
            )
        command = self.build_command(provider_key, request)
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=request.timeout_s,
            shell=False,
        )
        return CliInvocationResult(
            provider_key=provider_key,
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
