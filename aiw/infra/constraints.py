"""Constraints loading and validation utilities."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, is_dataclass
from pathlib import Path
from typing import cast

import yaml


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    stack: str


@dataclass(frozen=True)
class LayerConfig:
    name: str
    allowed_imports: list[str]


@dataclass(frozen=True)
class InternalToolStateConfig:
    paths: list[str]
    writer: str
    coding_agents_must_not_write: bool


@dataclass(frozen=True)
class LockAfterStateConfig:
    artifact: str
    state: str


@dataclass(frozen=True)
class LockedArtifactsConfig:
    always_locked: list[str]
    lock_after_state: list[LockAfterStateConfig]
    immutable_during_execution: list[str]
    mutable_during_execution_append_only: list[str]


@dataclass(frozen=True)
class ReapprovalTransitionConfig:
    from_state: str
    to_state: str
    reapprove_command: str


@dataclass(frozen=True)
class ChangeRequestConfig:
    file: str
    required_for_modifying_locked_artifacts: bool
    requires_reapproval_transition: dict[str, ReapprovalTransitionConfig]


@dataclass(frozen=True)
class BoundariesConfig:
    internal_tool_state: InternalToolStateConfig
    locked_artifacts: LockedArtifactsConfig
    change_request: ChangeRequestConfig


@dataclass(frozen=True)
class MemoryConfig:
    type: str
    path_template: str
    append_only: bool


@dataclass(frozen=True)
class TaskScopedCodingAgentConfig:
    enforced: bool
    task_id_regex: str
    no_cross_task_edits: bool
    memory: MemoryConfig


@dataclass(frozen=True)
class AgentsConfig:
    task_scoped_coding_agent: TaskScopedCodingAgentConfig


@dataclass(frozen=True)
class WriteScopeValidationConfig:
    enabled: bool
    allowed_edit_paths: list[str]
    forbid_paths: list[str]


@dataclass(frozen=True)
class DiffValidationConfig:
    enabled: bool
    max_files_changed: int
    max_lines_changed: int
    hard_fail_on_exceed: bool


@dataclass(frozen=True)
class QualityConfig:
    test_command: str | None
    lint_command: str | None
    typecheck_command: str | None


@dataclass(frozen=True)
class TracesConfig:
    required_events: list[str]


@dataclass(frozen=True)
class ObservabilityArtifactsConfig:
    jsonl_trace_path: str


@dataclass(frozen=True)
class ObservabilityConfig:
    traces: TracesConfig
    artifacts: ObservabilityArtifactsConfig


@dataclass(frozen=True)
class WorkflowTransitionConfig:
    from_state: str
    to: str
    command: str | None
    on: str | None


@dataclass(frozen=True)
class WorkflowConfig:
    state_file: str
    enforce_state_machine: bool
    illegal_actions_must_fail_hard: bool
    state_transitions_must_be_logged: bool
    states: list[str]
    allowed_commands_by_state: dict[str, list[str]]
    transitions: list[WorkflowTransitionConfig]


@dataclass(frozen=True)
class LockingRulesConfig:
    enforce_command_level_validation: bool
    forbid_silent_edits_to_locked_artifacts: bool
    hard_fail_on_locked_artifact_modification_during_executing: bool
    locked_artifacts_checked_via_git_diff_name_only: bool


@dataclass(frozen=True)
class TaskCompletionConfig:
    enabled: bool
    tracker_file: str
    append_only: bool
    mark_on_pass: bool


@dataclass(frozen=True)
class ConstraintsFinalizationGateConfig:
    enabled: bool
    required_non_placeholder_fields: list[str]
    placeholder_values: list[str]
    refuse_commands: list[str]


@dataclass(frozen=True)
class RunIdConfig:
    required: bool
    write_on_enter_executing: bool


@dataclass(frozen=True)
class OnDetectExecutingAtStartupConfig:
    transition_to: str
    emit_event: str


@dataclass(frozen=True)
class StaleExecutionPolicyConfig:
    enabled: bool
    on_detect_executing_at_startup: OnDetectExecutingAtStartupConfig


@dataclass(frozen=True)
class ExecutionConfig:
    max_iterations_per_task: int
    task_completion: TaskCompletionConfig
    constraints_finalization_gate: ConstraintsFinalizationGateConfig
    run_id: RunIdConfig
    stale_execution_policy: StaleExecutionPolicyConfig


@dataclass(frozen=True)
class ConstraintsConfig:
    project: ProjectConfig
    layers: list[LayerConfig]
    boundaries: BoundariesConfig
    agents: AgentsConfig
    write_scope_validation: WriteScopeValidationConfig
    diff_validation: DiffValidationConfig
    quality: QualityConfig
    observability: ObservabilityConfig
    workflow: WorkflowConfig
    locking_rules: LockingRulesConfig
    execution: ExecutionConfig


def load_constraints(path: Path) -> ConstraintsConfig:
    """Load and parse constraints YAML into a typed configuration object."""
    raw_text = path.read_text(encoding="utf-8")
    normalized = _normalize_backtick_scalars(raw_text)
    loaded = yaml.safe_load(normalized)
    root = _as_mapping(loaded, "root")

    return ConstraintsConfig(
        project=_parse_project(root),
        layers=_parse_layers(root),
        boundaries=_parse_boundaries(root),
        agents=_parse_agents(root),
        write_scope_validation=_parse_write_scope_validation(root),
        diff_validation=_parse_diff_validation(root),
        quality=_parse_quality(root),
        observability=_parse_observability(root),
        workflow=_parse_workflow(root),
        locking_rules=_parse_locking_rules(root),
        execution=_parse_execution(root),
    )


def validate_constraints(config: ConstraintsConfig) -> list[str]:
    """Validate gate-required fields and placeholder values."""
    errors: list[str] = []
    gate = config.execution.constraints_finalization_gate
    placeholders = set(gate.placeholder_values)

    for field_path in gate.required_non_placeholder_fields:
        exists, value = _resolve_path(config, field_path)
        if not exists or value is None:
            errors.append(f"Missing required field: {field_path}")
            continue

        if isinstance(value, str) and value in placeholders:
            errors.append(f"Field {field_path} contains placeholder value: {value!r}")

    return errors


def _parse_project(root: Mapping[str, object]) -> ProjectConfig:
    section = _as_mapping(_required(root, "project", "root"), "project")
    return ProjectConfig(
        name=_as_str(_required(section, "name", "project"), "project.name"),
        stack=_as_str(_required(section, "stack", "project"), "project.stack"),
    )


def _parse_layers(root: Mapping[str, object]) -> list[LayerConfig]:
    values = _as_list(_required(root, "layers", "root"), "layers")
    layers: list[LayerConfig] = []
    for index, value in enumerate(values):
        entry_path = f"layers[{index}]"
        item = _as_mapping(value, entry_path)
        layers.append(
            LayerConfig(
                name=_as_str(_required(item, "name", entry_path), f"{entry_path}.name"),
                allowed_imports=_as_str_list(
                    _required(item, "allowed_imports", entry_path),
                    f"{entry_path}.allowed_imports",
                ),
            )
        )
    return layers


def _parse_boundaries(root: Mapping[str, object]) -> BoundariesConfig:
    section = _as_mapping(_required(root, "boundaries", "root"), "boundaries")

    internal_tool_state_map = _as_mapping(
        _required(section, "internal_tool_state", "boundaries"),
        "boundaries.internal_tool_state",
    )
    internal_tool_state = InternalToolStateConfig(
        paths=_as_str_list(
            _required(
                internal_tool_state_map, "paths", "boundaries.internal_tool_state"
            ),
            "boundaries.internal_tool_state.paths",
        ),
        writer=_as_str(
            _required(
                internal_tool_state_map, "writer", "boundaries.internal_tool_state"
            ),
            "boundaries.internal_tool_state.writer",
        ),
        coding_agents_must_not_write=_as_bool(
            _required(
                internal_tool_state_map,
                "coding_agents_must_not_write",
                "boundaries.internal_tool_state",
            ),
            "boundaries.internal_tool_state.coding_agents_must_not_write",
        ),
    )

    locked_artifacts_map = _as_mapping(
        _required(section, "locked_artifacts", "boundaries"),
        "boundaries.locked_artifacts",
    )
    lock_after_state_values = _as_list(
        _required(
            locked_artifacts_map, "lock_after_state", "boundaries.locked_artifacts"
        ),
        "boundaries.locked_artifacts.lock_after_state",
    )
    lock_after_state: list[LockAfterStateConfig] = []
    for index, value in enumerate(lock_after_state_values):
        entry_path = f"boundaries.locked_artifacts.lock_after_state[{index}]"
        item = _as_mapping(value, entry_path)
        lock_after_state.append(
            LockAfterStateConfig(
                artifact=_as_str(
                    _required(item, "artifact", entry_path), f"{entry_path}.artifact"
                ),
                state=_as_str(
                    _required(item, "state", entry_path), f"{entry_path}.state"
                ),
            )
        )

    locked_artifacts = LockedArtifactsConfig(
        always_locked=_as_str_list(
            _required(
                locked_artifacts_map, "always_locked", "boundaries.locked_artifacts"
            ),
            "boundaries.locked_artifacts.always_locked",
        ),
        lock_after_state=lock_after_state,
        immutable_during_execution=_as_str_list(
            _required(
                locked_artifacts_map,
                "immutable_during_execution",
                "boundaries.locked_artifacts",
            ),
            "boundaries.locked_artifacts.immutable_during_execution",
        ),
        mutable_during_execution_append_only=_as_str_list(
            _required(
                locked_artifacts_map,
                "mutable_during_execution_append_only",
                "boundaries.locked_artifacts",
            ),
            "boundaries.locked_artifacts.mutable_during_execution_append_only",
        ),
    )

    change_request_map = _as_mapping(
        _required(section, "change_request", "boundaries"),
        "boundaries.change_request",
    )
    transitions_map = _as_mapping(
        _required(
            change_request_map,
            "requires_reapproval_transition",
            "boundaries.change_request",
        ),
        "boundaries.change_request.requires_reapproval_transition",
    )
    transitions: dict[str, ReapprovalTransitionConfig] = {}
    for key, value in transitions_map.items():
        item_path = f"boundaries.change_request.requires_reapproval_transition.{key}"
        item = _as_mapping(value, item_path)
        transitions[key] = ReapprovalTransitionConfig(
            from_state=_as_str(
                _required(item, "from_state", item_path), f"{item_path}.from_state"
            ),
            to_state=_as_str(
                _required(item, "to_state", item_path), f"{item_path}.to_state"
            ),
            reapprove_command=_as_str(
                _required(item, "reapprove_command", item_path),
                f"{item_path}.reapprove_command",
            ),
        )

    change_request = ChangeRequestConfig(
        file=_as_str(
            _required(change_request_map, "file", "boundaries.change_request"),
            "boundaries.change_request.file",
        ),
        required_for_modifying_locked_artifacts=_as_bool(
            _required(
                change_request_map,
                "required_for_modifying_locked_artifacts",
                "boundaries.change_request",
            ),
            "boundaries.change_request.required_for_modifying_locked_artifacts",
        ),
        requires_reapproval_transition=transitions,
    )

    return BoundariesConfig(
        internal_tool_state=internal_tool_state,
        locked_artifacts=locked_artifacts,
        change_request=change_request,
    )


def _parse_agents(root: Mapping[str, object]) -> AgentsConfig:
    section = _as_mapping(_required(root, "agents", "root"), "agents")
    task_scoped = _as_mapping(
        _required(section, "task_scoped_coding_agent", "agents"),
        "agents.task_scoped_coding_agent",
    )
    memory_map = _as_mapping(
        _required(task_scoped, "memory", "agents.task_scoped_coding_agent"),
        "agents.task_scoped_coding_agent.memory",
    )

    memory = MemoryConfig(
        type=_as_str(
            _required(memory_map, "type", "agents.task_scoped_coding_agent.memory"),
            "agents.task_scoped_coding_agent.memory.type",
        ),
        path_template=_as_str(
            _required(
                memory_map, "path_template", "agents.task_scoped_coding_agent.memory"
            ),
            "agents.task_scoped_coding_agent.memory.path_template",
        ),
        append_only=_as_bool(
            _required(
                memory_map, "append_only", "agents.task_scoped_coding_agent.memory"
            ),
            "agents.task_scoped_coding_agent.memory.append_only",
        ),
    )

    return AgentsConfig(
        task_scoped_coding_agent=TaskScopedCodingAgentConfig(
            enforced=_as_bool(
                _required(task_scoped, "enforced", "agents.task_scoped_coding_agent"),
                "agents.task_scoped_coding_agent.enforced",
            ),
            task_id_regex=_as_str(
                _required(
                    task_scoped, "task_id_regex", "agents.task_scoped_coding_agent"
                ),
                "agents.task_scoped_coding_agent.task_id_regex",
            ),
            no_cross_task_edits=_as_bool(
                _required(
                    task_scoped,
                    "no_cross_task_edits",
                    "agents.task_scoped_coding_agent",
                ),
                "agents.task_scoped_coding_agent.no_cross_task_edits",
            ),
            memory=memory,
        )
    )


def _parse_write_scope_validation(
    root: Mapping[str, object],
) -> WriteScopeValidationConfig:
    section = _as_mapping(
        _required(root, "write_scope_validation", "root"),
        "write_scope_validation",
    )
    return WriteScopeValidationConfig(
        enabled=_as_bool(
            _required(section, "enabled", "write_scope_validation"),
            "write_scope_validation.enabled",
        ),
        allowed_edit_paths=_as_str_list(
            _required(section, "allowed_edit_paths", "write_scope_validation"),
            "write_scope_validation.allowed_edit_paths",
        ),
        forbid_paths=_as_str_list(
            _required(section, "forbid_paths", "write_scope_validation"),
            "write_scope_validation.forbid_paths",
        ),
    )


def _parse_diff_validation(root: Mapping[str, object]) -> DiffValidationConfig:
    section = _as_mapping(_required(root, "diff_validation", "root"), "diff_validation")
    return DiffValidationConfig(
        enabled=_as_bool(
            _required(section, "enabled", "diff_validation"),
            "diff_validation.enabled",
        ),
        max_files_changed=_as_int(
            _required(section, "max_files_changed", "diff_validation"),
            "diff_validation.max_files_changed",
        ),
        max_lines_changed=_as_int(
            _required(section, "max_lines_changed", "diff_validation"),
            "diff_validation.max_lines_changed",
        ),
        hard_fail_on_exceed=_as_bool(
            _required(section, "hard_fail_on_exceed", "diff_validation"),
            "diff_validation.hard_fail_on_exceed",
        ),
    )


def _parse_quality(root: Mapping[str, object]) -> QualityConfig:
    section = _as_mapping(_required(root, "quality", "root"), "quality")
    return QualityConfig(
        test_command=_optional_str(section, "test_command", "quality"),
        lint_command=_optional_str(section, "lint_command", "quality"),
        typecheck_command=_optional_str(section, "typecheck_command", "quality"),
    )


def _parse_observability(root: Mapping[str, object]) -> ObservabilityConfig:
    section = _as_mapping(_required(root, "observability", "root"), "observability")
    traces_map = _as_mapping(
        _required(section, "traces", "observability"),
        "observability.traces",
    )
    artifacts_map = _as_mapping(
        _required(section, "artifacts", "observability"),
        "observability.artifacts",
    )

    return ObservabilityConfig(
        traces=TracesConfig(
            required_events=_as_str_list(
                _required(traces_map, "required_events", "observability.traces"),
                "observability.traces.required_events",
            )
        ),
        artifacts=ObservabilityArtifactsConfig(
            jsonl_trace_path=_as_str(
                _required(artifacts_map, "jsonl_trace_path", "observability.artifacts"),
                "observability.artifacts.jsonl_trace_path",
            )
        ),
    )


def _parse_workflow(root: Mapping[str, object]) -> WorkflowConfig:
    section = _as_mapping(_required(root, "workflow", "root"), "workflow")
    allowed_commands_map = _as_mapping(
        _required(section, "allowed_commands_by_state", "workflow"),
        "workflow.allowed_commands_by_state",
    )
    allowed_commands_by_state: dict[str, list[str]] = {}
    for state, commands in allowed_commands_map.items():
        allowed_commands_by_state[state] = _as_str_list(
            commands, f"workflow.allowed_commands_by_state.{state}"
        )

    transitions_values = _as_list(
        _required(section, "transitions", "workflow"),
        "workflow.transitions",
    )
    transitions: list[WorkflowTransitionConfig] = []
    for index, value in enumerate(transitions_values):
        item_path = f"workflow.transitions[{index}]"
        item = _as_mapping(value, item_path)
        command = _optional_str(item, "command", item_path)
        on_value = _optional_str(item, "on", item_path)
        if command is None and on_value is None:
            raise ValueError(f"{item_path} must include one of 'command' or 'on'")
        if command is not None and on_value is not None:
            raise ValueError(f"{item_path} cannot define both 'command' and 'on'")

        transitions.append(
            WorkflowTransitionConfig(
                from_state=_as_str(
                    _required(item, "from", item_path), f"{item_path}.from"
                ),
                to=_as_str(_required(item, "to", item_path), f"{item_path}.to"),
                command=command,
                on=on_value,
            )
        )

    return WorkflowConfig(
        state_file=_as_str(
            _required(section, "state_file", "workflow"), "workflow.state_file"
        ),
        enforce_state_machine=_as_bool(
            _required(section, "enforce_state_machine", "workflow"),
            "workflow.enforce_state_machine",
        ),
        illegal_actions_must_fail_hard=_as_bool(
            _required(section, "illegal_actions_must_fail_hard", "workflow"),
            "workflow.illegal_actions_must_fail_hard",
        ),
        state_transitions_must_be_logged=_as_bool(
            _required(section, "state_transitions_must_be_logged", "workflow"),
            "workflow.state_transitions_must_be_logged",
        ),
        states=_as_str_list(
            _required(section, "states", "workflow"), "workflow.states"
        ),
        allowed_commands_by_state=allowed_commands_by_state,
        transitions=transitions,
    )


def _parse_locking_rules(root: Mapping[str, object]) -> LockingRulesConfig:
    section = _as_mapping(_required(root, "locking_rules", "root"), "locking_rules")
    return LockingRulesConfig(
        enforce_command_level_validation=_as_bool(
            _required(section, "enforce_command_level_validation", "locking_rules"),
            "locking_rules.enforce_command_level_validation",
        ),
        forbid_silent_edits_to_locked_artifacts=_as_bool(
            _required(
                section, "forbid_silent_edits_to_locked_artifacts", "locking_rules"
            ),
            "locking_rules.forbid_silent_edits_to_locked_artifacts",
        ),
        hard_fail_on_locked_artifact_modification_during_executing=_as_bool(
            _required(
                section,
                "hard_fail_on_locked_artifact_modification_during_EXECUTING",
                "locking_rules",
            ),
            "locking_rules.hard_fail_on_locked_artifact_modification_during_EXECUTING",
        ),
        locked_artifacts_checked_via_git_diff_name_only=_as_bool(
            _required(
                section,
                "locked_artifacts_checked_via_git_diff_name_only",
                "locking_rules",
            ),
            "locking_rules.locked_artifacts_checked_via_git_diff_name_only",
        ),
    )


def _parse_execution(root: Mapping[str, object]) -> ExecutionConfig:
    section = _as_mapping(_required(root, "execution", "root"), "execution")

    task_completion_map = _as_mapping(
        _required(section, "task_completion", "execution"),
        "execution.task_completion",
    )
    task_completion = TaskCompletionConfig(
        enabled=_as_bool(
            _required(task_completion_map, "enabled", "execution.task_completion"),
            "execution.task_completion.enabled",
        ),
        tracker_file=_as_str(
            _required(task_completion_map, "tracker_file", "execution.task_completion"),
            "execution.task_completion.tracker_file",
        ),
        append_only=_as_bool(
            _required(task_completion_map, "append_only", "execution.task_completion"),
            "execution.task_completion.append_only",
        ),
        mark_on_pass=_as_bool(
            _required(task_completion_map, "mark_on_pass", "execution.task_completion"),
            "execution.task_completion.mark_on_pass",
        ),
    )

    gate_map = _as_mapping(
        _required(section, "constraints_finalization_gate", "execution"),
        "execution.constraints_finalization_gate",
    )
    gate = ConstraintsFinalizationGateConfig(
        enabled=_as_bool(
            _required(gate_map, "enabled", "execution.constraints_finalization_gate"),
            "execution.constraints_finalization_gate.enabled",
        ),
        required_non_placeholder_fields=_as_str_list(
            _required(
                gate_map,
                "required_non_placeholder_fields",
                "execution.constraints_finalization_gate",
            ),
            "execution.constraints_finalization_gate.required_non_placeholder_fields",
        ),
        placeholder_values=_as_str_list(
            _required(
                gate_map,
                "placeholder_values",
                "execution.constraints_finalization_gate",
            ),
            "execution.constraints_finalization_gate.placeholder_values",
        ),
        refuse_commands=_as_str_list(
            _required(
                gate_map, "refuse_commands", "execution.constraints_finalization_gate"
            ),
            "execution.constraints_finalization_gate.refuse_commands",
        ),
    )

    run_id_map = _as_mapping(
        _required(section, "run_id", "execution"), "execution.run_id"
    )
    run_id = RunIdConfig(
        required=_as_bool(
            _required(run_id_map, "required", "execution.run_id"),
            "execution.run_id.required",
        ),
        write_on_enter_executing=_as_bool(
            _required(run_id_map, "write_on_enter_EXECUTING", "execution.run_id"),
            "execution.run_id.write_on_enter_EXECUTING",
        ),
    )

    stale_policy_map = _as_mapping(
        _required(section, "stale_execution_policy", "execution"),
        "execution.stale_execution_policy",
    )
    on_detect_map = _as_mapping(
        _required(
            stale_policy_map,
            "on_detect_EXECUTING_at_startup",
            "execution.stale_execution_policy",
        ),
        "execution.stale_execution_policy.on_detect_EXECUTING_at_startup",
    )
    stale_policy = StaleExecutionPolicyConfig(
        enabled=_as_bool(
            _required(stale_policy_map, "enabled", "execution.stale_execution_policy"),
            "execution.stale_execution_policy.enabled",
        ),
        on_detect_executing_at_startup=OnDetectExecutingAtStartupConfig(
            transition_to=_as_str(
                _required(
                    on_detect_map,
                    "transition_to",
                    "execution.stale_execution_policy.on_detect_EXECUTING_at_startup",
                ),
                "execution.stale_execution_policy.on_detect_EXECUTING_at_startup.transition_to",
            ),
            emit_event=_as_str(
                _required(
                    on_detect_map,
                    "emit_event",
                    "execution.stale_execution_policy.on_detect_EXECUTING_at_startup",
                ),
                "execution.stale_execution_policy.on_detect_EXECUTING_at_startup.emit_event",
            ),
        ),
    )

    return ExecutionConfig(
        max_iterations_per_task=_as_int(
            _required(section, "max_iterations_per_task", "execution"),
            "execution.max_iterations_per_task",
        ),
        task_completion=task_completion,
        constraints_finalization_gate=gate,
        run_id=run_id,
        stale_execution_policy=stale_policy,
    )


def _required(data: Mapping[str, object], key: str, path: str) -> object:
    if key not in data:
        raise ValueError(f"Missing required key '{key}' at {path}")
    return data[key]


def _as_mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Expected mapping at {path}")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"Expected string keys for mapping at {path}")
    return cast(Mapping[str, object], value)


def _as_list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"Expected list at {path}")
    return value


def _as_str_list(value: object, path: str) -> list[str]:
    values = _as_list(value, path)
    result: list[str] = []
    for index, item in enumerate(values):
        if not isinstance(item, str):
            raise ValueError(f"Expected string at {path}[{index}]")
        result.append(item)
    return result


def _as_str(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Expected string at {path}")
    return value


def _as_bool(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"Expected boolean at {path}")
    return value


def _as_int(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Expected integer at {path}")
    return value


def _optional_str(data: Mapping[str, object], key: str, path: str) -> str | None:
    if key not in data:
        return None
    value = data[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Expected string at {path}.{key}")
    return value


def _normalize_backtick_scalars(raw_text: str) -> str:
    """Normalize known YAML 1.1 edge cases present in constraints.yml."""
    normalized = re.sub(
        r"^(\s*)on:(\s+)",
        r'\1"on":\2',
        raw_text,
        flags=re.MULTILINE,
    )
    pattern = re.compile(r"^(\s*[^#\n][^:\n]*:\s*)(`[^`\n]*`)\s*$", re.MULTILINE)

    def repl(match: re.Match[str]) -> str:
        prefix = match.group(1)
        value = match.group(2)
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{prefix}"{escaped}"'

    return pattern.sub(repl, normalized)


def _resolve_path(
    config: ConstraintsConfig, field_path: str
) -> tuple[bool, object | None]:
    current: object = config
    for part in field_path.split("."):
        if is_dataclass(current):
            if not hasattr(current, part):
                return False, None
            current = getattr(current, part)
            continue

        if isinstance(current, Mapping):
            mapping = _as_mapping(current, field_path)
            if part not in mapping:
                return False, None
            current = mapping[part]
            continue

        return False, None
    return True, current


__all__ = ["ConstraintsConfig", "load_constraints", "validate_constraints"]
