"""The pinned structural indexer's node vocabulary stays fully mapped.

Unit tests pin the mapping table against synthetic wiring. This lane runs
the real indexer, so a provider release that starts emitting a new node
kind fails here instead of failing a user's first `initialize_repository`.

Rust is the language that surfaced the gap: `mod` and `const` nodes have
no callable or type shape, and an unmapped kind fails the whole load.
"""

import pathlib
import shutil
import subprocess
import tempfile
import unittest

from span.core import model as m
from span.shell.structural.graft import (
    STRUCTURAL_INDEXER_VERSION,
    GraftStructuralSource,
    _run_index_build,
    resolve_indexer_binary,
)

_RUST_SOURCE = """pub mod inner;

pub const MAX_RETRIES: i32 = 3;
pub static COUNTER: i32 = 0;

pub struct Service {
    pub name: String,
}

impl Service {
    pub fn run(&self) -> i32 {
        1
    }
}
"""

_GIT_IDENTITY = (
    "-c",
    "user.email=test@example.invalid",
    "-c",
    "user.name=test",
)


class ProviderVocabularyLaneTest(unittest.TestCase):
    def setUp(self):
        binary = resolve_indexer_binary()
        if binary is None:
            self.skipTest("structural indexer not provisioned")
        try:
            version = subprocess.run(
                (binary, "--version"),
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            self.skipTest(f"structural indexer unusable: {exc}")
        if version != STRUCTURAL_INDEXER_VERSION:
            self.skipTest(
                f"indexer {version} differs from the pinned "
                f"{STRUCTURAL_INDEXER_VERSION}; vocabulary is pinned too"
            )

    def test_rust_module_and_constant_load_without_vocabulary_error(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="span-vocabulary-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = tmp / "repo"
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "lib.rs").write_text(_RUST_SOURCE, encoding="utf-8")
        for args in (
            ("init", "-q"),
            ("add", "-A"),
            (*_GIT_IDENTITY, "commit", "-qm", "fixture"),
        ):
            subprocess.run(
                ("git", "-C", str(repo), *args),
                check=True,
                capture_output=True,
                timeout=120,
            )

        artifact = tmp / "cache"
        ok, detail = _run_index_build(repo, artifact)
        self.assertTrue(ok, detail)

        source = GraftStructuralSource("vocabulary-repo", repo, artifact_dir=artifact)
        self.assertIsNone(
            source._load_error,
            f"provider vocabulary rejected: {source._load_error}",
        )
        subjects = {node_id: source._to_subject(node_id) for node_id in source._nodes}
        constant = next(
            subject
            for node_id, subject in subjects.items()
            if node_id.endswith("#MAX_RETRIES")
        )
        self.assertIs(
            constant.subject_id.subject_kind,
            m.SubjectKind.CODE_SYMBOL,
        )
        module = next(
            subject
            for node_id, subject in subjects.items()
            if node_id.endswith("#inner")
        )
        self.assertIs(module.subject_id.subject_kind, m.SubjectKind.COMPONENT)


if __name__ == "__main__":
    unittest.main()
