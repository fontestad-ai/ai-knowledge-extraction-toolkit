"""Tests for the local CLI model runtime registry."""

from gaik.software_components.llm import (
    CliInvocationRequest,
    CliModelRuntime,
    get_default_cli_runtime_targets,
)


def test_cli_runtime_registry_exposes_expected_targets():
    runtime = CliModelRuntime()
    provider_keys = {target.provider_key for target in runtime.list_targets()}

    assert "claude_code_cli" in provider_keys
    assert "github_copilot_cli" in provider_keys
    assert "snowflake_cortex_cli" in provider_keys


def test_cli_runtime_builds_shell_free_command():
    runtime = CliModelRuntime()
    request = CliInvocationRequest(
        prompt="Validate this extraction",
        system_prompt="Be precise",
        model="test-model",
        extra_args=("--json",),
    )

    command = runtime.build_command("codex_cli", request)

    assert command[0] == "codex"
    assert "--model" in command
    assert "--prompt" in command
    assert "Validate this extraction" in command


def test_default_cli_targets_match_public_registry_helper():
    runtime = CliModelRuntime()

    assert runtime.list_targets() == get_default_cli_runtime_targets()
