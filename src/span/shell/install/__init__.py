"""Cross-platform-capable Span installer (Linux implemented).

Stdlib only at import time. No semantic ``span.*`` imports: this package
must run from a source checkout (via ``scripts/install-span.py``) before
Span is installed, and post-install as the ``span-install`` entry point.
All semantic imports are lazy inside verification paths.

OS specifics live exclusively in ``PLATFORM_PATHS``; ``linux`` is fully
specified, ``darwin``/``win32`` are structurally reserved.
"""

from __future__ import annotations

from span.shell.install.arguments import (  # noqa: F401
    parse_args,
)
from span.shell.install.backup import (  # noqa: F401
    backup_data_dir,
    snapshot_census,
    compare_census,
    _clean_build_staging,
    target_artifact_snapshot,
)
from span.shell.install.constants import (  # noqa: F401
    INSTALL_VERSION,
    STRUCTURAL_INDEXER_PACKAGE,
    STRUCTURAL_INDEXER_VERSION,
    PLATFORM_PATHS,
    AGENTS_START,
    AGENTS_END,
    _VERSION_PROBE,
)
from span.shell.install.host_inspect import (  # noqa: F401
    detect_hosts,
    inspect_opencode_registration,
    inspect_codex_registration,
    inspect_claude_registration,
)
from span.shell.install.hosts import (  # noqa: F401
    merge_opencode_config,
    remove_opencode_registration,
    register_codex,
    register_claude,
    _hook_bin,
    wire_codex_hooks,
    wire_claude_hooks,
    remove_codex_registration,
    remove_claude_registration,
    _span_hook_command,
    _remove_span_hooks,
    remove_codex_hooks,
    remove_claude_hooks,
)
from span.shell.install.indexer import (  # noqa: F401
    check_prereqs,
    _redact_provider,
    ensure_structural_indexer,
    write_indexer_pointer,
)
from span.shell.install.paths import (  # noqa: F401
    platform_paths,
    default_tools_dir,
    indexer_binary_path,
    install_mode,
    distribution_version,
    bundled_assets_root,
    canonical_skills_dir,
    agents_snippet_path,
    git_rev,
    expected_span_command,
)
from span.shell.install.preflight import (  # noqa: F401
    load_seeds,
    preflight_facts,
)
from span.shell.install.receipt import (  # noqa: F401
    write_receipt,
    read_receipt,
)
from span.shell.install.skills import (  # noqa: F401
    ensure_agents_rule,
    remove_agents_block,
    deploy_agents_rules,
    deploy_skills,
    check_skills,
    remove_deployed_skills,
)
from span.shell.install.uninstall import (  # noqa: F401
    uninstall,
    _valid_repository_id,
    purge_repository,
    _present_repository_ids,
    list_orphans,
)
from span.shell.install.venv import (  # noqa: F401
    _run,
    ensure_venv,
    _has_venv_pip,
    _hash_tree,
    source_venv_in_sync,
    distribution_venv_in_sync,
    pip_install,
    verify_installed,
    expose_binary,
)
from span.shell.install.verify import (  # noqa: F401
    verify_installation,
    doctor,
)
from span.shell.install.cli import main  # noqa: F401

__all__ = [
    "parse_args",
    "backup_data_dir",
    "snapshot_census",
    "compare_census",
    "_clean_build_staging",
    "target_artifact_snapshot",
    "INSTALL_VERSION",
    "STRUCTURAL_INDEXER_PACKAGE",
    "STRUCTURAL_INDEXER_VERSION",
    "PLATFORM_PATHS",
    "AGENTS_START",
    "AGENTS_END",
    "_VERSION_PROBE",
    "detect_hosts",
    "inspect_opencode_registration",
    "inspect_codex_registration",
    "inspect_claude_registration",
    "merge_opencode_config",
    "remove_opencode_registration",
    "register_codex",
    "register_claude",
    "_hook_bin",
    "wire_codex_hooks",
    "wire_claude_hooks",
    "remove_codex_registration",
    "remove_claude_registration",
    "_span_hook_command",
    "_remove_span_hooks",
    "remove_codex_hooks",
    "remove_claude_hooks",
    "check_prereqs",
    "_redact_provider",
    "ensure_structural_indexer",
    "write_indexer_pointer",
    "platform_paths",
    "default_tools_dir",
    "indexer_binary_path",
    "install_mode",
    "distribution_version",
    "bundled_assets_root",
    "canonical_skills_dir",
    "agents_snippet_path",
    "git_rev",
    "expected_span_command",
    "load_seeds",
    "preflight_facts",
    "write_receipt",
    "read_receipt",
    "ensure_agents_rule",
    "remove_agents_block",
    "deploy_agents_rules",
    "deploy_skills",
    "check_skills",
    "remove_deployed_skills",
    "uninstall",
    "_valid_repository_id",
    "purge_repository",
    "_present_repository_ids",
    "list_orphans",
    "_run",
    "ensure_venv",
    "_has_venv_pip",
    "_hash_tree",
    "source_venv_in_sync",
    "distribution_venv_in_sync",
    "pip_install",
    "verify_installed",
    "expose_binary",
    "verify_installation",
    "doctor",
    "main",
]
