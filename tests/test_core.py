"""Unit tests for the conversion core (no GUI and no CLI required)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sog_converter import core


class OptionsTests(unittest.TestCase):
    def test_decimate_arg(self):
        self.assertIsNone(core.Options(decimate_mode="keep").decimate_arg())
        self.assertEqual(core.Options(decimate_mode="count", decimate_value=400000).decimate_arg(), "400000")
        self.assertEqual(core.Options(decimate_mode="percent", decimate_value=34).decimate_arg(), "34%")

    def test_decimate_arg_rejects_bad_values(self):
        with self.assertRaises(ValueError):
            core.Options(decimate_mode="count", decimate_value=0, output_dir=Path(".")).validate()
        with self.assertRaises(ValueError):
            core.Options(decimate_mode="percent", decimate_value=120, output_dir=Path(".")).validate()
        with self.assertRaises(ValueError):
            core.Options(decimate_mode="bogus", output_dir=Path(".")).validate()

    def test_validate_requires_output_dir_unless_replacing(self):
        with self.assertRaises(ValueError):
            core.Options().validate()
        core.Options(replace_source=True).validate()

    def test_validate_webp_effort(self):
        with self.assertRaises(ValueError):
            core.Options(output_dir=Path("."), webp_effort=12).validate()


class CollectInputsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "a.ply").write_bytes(b"x")
        (self.root / "b.spz").write_bytes(b"x")
        (self.root / "c.txt").write_bytes(b"x")
        (self.root / "d.sog").write_bytes(b"x")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "e.ply").write_bytes(b"x")
        (self.root / "sub" / ".hidden.ply.__tmp__.sog").write_bytes(b"x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_recursive(self):
        found = core.collect_inputs([self.root], recursive=True)
        self.assertEqual([p.name for p in found], ["a.ply", "b.spz", "e.ply"])

    def test_non_recursive(self):
        found = core.collect_inputs([self.root], recursive=False)
        self.assertEqual([p.name for p in found], ["a.ply", "b.spz"])

    def test_single_file_and_dedup(self):
        target = self.root / "a.ply"
        found = core.collect_inputs([target, target, self.root / "sub" / "e.ply"])
        self.assertEqual(len(found), 2)

    def test_is_supported(self):
        self.assertTrue(core.is_supported(Path("x.ply")))
        self.assertTrue(core.is_supported(Path("x.compressed.ply")))
        self.assertFalse(core.is_supported(Path("x.sog")))
        self.assertFalse(core.is_supported(Path("x.txt")))


class PlanJobsTests(unittest.TestCase):
    def test_output_dir(self):
        sources = [Path("/data/one.ply"), Path("/data/two.spz")]
        opts = core.Options(output_dir=Path("/out"))
        jobs = core.plan_jobs(sources, opts)
        self.assertEqual([j.target.name for j in jobs], ["one.sog", "two.sog"])
        self.assertEqual(jobs[0].target.parent, Path("/out"))

    def test_name_collision_gets_suffix(self):
        sources = [Path("/a/one.ply"), Path("/b/one.ply")]
        jobs = core.plan_jobs(sources, core.Options(output_dir=Path("/out")))
        self.assertEqual([j.target.name for j in jobs], ["one.sog", "one_2.sog"])

    def test_replace_source_writes_next_to_source(self):
        sources = [Path("/a/one.ply")]
        jobs = core.plan_jobs(sources, core.Options(replace_source=True))
        self.assertEqual(jobs[0].target, Path("/a/one.sog"))


class RunConversionTests(unittest.TestCase):
    def test_skips_existing_output_without_calling_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "scene.ply"
            source.write_bytes(b"x")
            target = root / "scene.sog"
            target.write_bytes(b"existing")
            opts = core.Options(output_dir=root, overwrite_existing=False)
            report = core.run_conversion([core.Job(source, target)], opts, "no-such-cli")
            self.assertEqual(report.skipped, 1)
            self.assertEqual(report.converted, 0)
            self.assertEqual(target.read_bytes(), b"existing")


class CliDiscoveryTests(unittest.TestCase):
    def test_env_override_wins(self):
        with mock.patch.dict(os.environ, {"SPLAT_TRANSFORM": "/custom/splat"}):
            with mock.patch.object(core.shutil, "which", return_value="/custom/splat"):
                self.assertEqual(core.find_cli(), "/custom/splat")


if __name__ == "__main__":
    unittest.main(verbosity=2)
