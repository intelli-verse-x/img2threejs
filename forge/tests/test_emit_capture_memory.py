"""Regression: verbose target output must not be fully captured in parent RAM."""
import sys
import tempfile
import tracemalloc
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "forge"))
sys.path.insert(0, str(ROOT / "forge" / "_shared"))
sys.path.insert(0, str(ROOT / "forge" / "stage3_build"))
import emit_target


class CaptureMemoryTest(unittest.TestCase):
    def test_large_output_has_bounded_parent_capture_memory(self):
        with tempfile.TemporaryDirectory() as workspace:
            tracemalloc.start()
            try:
                proc = emit_target.run_bounded(
                    [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x' * (20 * 1024 * 1024)); sys.stderr.buffer.write(b'y' * (128 * 1024))"],
                    cwd=Path(workspace), timeout=10, declared_env=[], target_kind="fixture",
                )
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"x" * emit_target.MAX_STDOUT_BYTES)
        self.assertEqual(proc.stderr, b"y" * emit_target.MAX_STDERR_BYTES)
        self.assertLess(peak, 8 * 1024 * 1024, "parent buffered the verbose child output")


class ArtifactLocationTest(unittest.TestCase):
    def test_symlink_cannot_redirect_failure_cleanup_outside_plugin_artifacts(self):
        from targets import Target
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            outside = root / "unrelated"
            outside.mkdir()
            sentinel = outside / "model.glb"
            sentinel.write_bytes(b"unrelated existing data")
            artifact_root = workspace / ".img2" / "artifacts"
            artifact_root.mkdir(parents=True)
            (artifact_root / "fixture").symlink_to(outside, target_is_directory=True)
            spec = workspace / "spec.json"
            spec.write_text("{}")
            target = Target(kind="glb", plugin_id="fixture", plugin_dir=root,
                            plugin_version="1.0.0", resolved_sha="fixture",
                            command="python3 -c pass", step_id="emit",
                            artifact_kind="glb", artifact_path=".img2/artifacts/fixture/model.glb",
                            deterministic=False, timeout_seconds=1)
            with mock.patch.object(emit_target, "run_bounded") as runner:
                with self.assertRaisesRegex(emit_target.EmitTargetError, "escapes allowed artifact directory"):
                    emit_target._run_plugin_target(target, spec_path=spec, workspace=workspace)
                runner.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b"unrelated existing data")
