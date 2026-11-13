"""Regression: verbose target output must not be fully captured in parent RAM."""
import sys
import tempfile
import tracemalloc
import unittest
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
