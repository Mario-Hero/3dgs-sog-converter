"""Tests for the bilingual string table and language selection."""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path
from unittest import mock

from sog_converter import core, i18n

_PLACEHOLDER = re.compile(r"\{(\w+)")


class StringTableTests(unittest.TestCase):
    def setUp(self):
        self.saved = i18n.get_language()

    def tearDown(self):
        i18n.set_language(self.saved)

    def test_key_sets_match(self):
        zh = set(i18n.STRINGS[i18n.ZH])
        en = set(i18n.STRINGS[i18n.EN])
        self.assertEqual(zh - en, set(), "keys missing in English")
        self.assertEqual(en - zh, set(), "keys missing in Chinese")

    def test_no_empty_values(self):
        for lang, table in i18n.STRINGS.items():
            for key, value in table.items():
                self.assertTrue(value.strip(), f"{lang}.{key} is empty")

    def test_placeholders_match(self):
        for key in i18n.STRINGS[i18n.ZH]:
            zh = set(_PLACEHOLDER.findall(i18n.STRINGS[i18n.ZH][key]))
            en = set(_PLACEHOLDER.findall(i18n.STRINGS[i18n.EN][key]))
            self.assertEqual(zh, en, f"placeholder mismatch for {key}")

    def test_translation_and_fallback(self):
        i18n.set_language("zh")
        self.assertEqual(i18n.t("btn_start"), "开始转换")
        i18n.set_language("en")
        self.assertEqual(i18n.t("btn_start"), "Start conversion")
        self.assertEqual(i18n.t("no_such_key"), "no_such_key")

    def test_formatting(self):
        i18n.set_language("en")
        self.assertEqual(i18n.t("log_added_files", count=3), "Added 3 file(s)")
        self.assertEqual(i18n.t("done", name="a.sog", size=1.234), "Done -> a.sog (1.23 MB)")

    def test_bad_format_args_do_not_crash(self):
        i18n.set_language("en")
        self.assertEqual(i18n.t("log_added_files"), "Added {count} file(s)")

    def test_invalid_language(self):
        with self.assertRaises(ValueError):
            i18n.set_language("fr")

    def test_normalize(self):
        self.assertEqual(i18n.normalize("zh-CN"), "zh")
        self.assertEqual(i18n.normalize("zh_TW"), "zh")
        self.assertEqual(i18n.normalize("en-US"), "en")
        self.assertIsNone(i18n.normalize("de"))

    def test_explicit_language_tracked(self):
        self.assertEqual(i18n.set_language("zh"), "zh")
        self.assertEqual(i18n.get_explicit_language(), "zh")
        i18n.set_language("auto")
        self.assertIsNone(i18n.get_explicit_language())


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.saved = i18n.get_language()

    def tearDown(self):
        i18n.set_language(self.saved)

    def test_sog_lang_override(self):
        with mock.patch.dict(os.environ, {"SOG_LANG": "zh"}, clear=False):
            self.assertEqual(i18n.detect_system_language(), "zh")
        with mock.patch.dict(os.environ, {"SOG_LANG": "en-US"}, clear=False):
            self.assertEqual(i18n.detect_system_language(), "en")

    def test_auto_delegates_to_detection(self):
        with mock.patch.object(i18n, "detect_system_language", return_value="en"):
            self.assertEqual(i18n.set_language("auto"), "en")


class CoreLocalisationTests(unittest.TestCase):
    def setUp(self):
        self.saved = i18n.get_language()

    def tearDown(self):
        i18n.set_language(self.saved)

    def test_error_message_follows_language(self):
        i18n.set_language("en")
        with self.assertRaises(ValueError) as ctx:
            core.Options(decimate_mode="count", decimate_value=0,
                         output_dir=Path(".")).validate()
        self.assertIn("greater than 0", str(ctx.exception))

        i18n.set_language("zh")
        with self.assertRaises(ValueError) as ctx:
            core.Options(decimate_mode="count", decimate_value=0,
                         output_dir=Path(".")).validate()
        self.assertIn("大于 0", str(ctx.exception))

    def test_skip_message_follows_language(self):
        import tempfile

        i18n.set_language("en")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "scene.ply"
            source.write_bytes(b"x")
            target = root / "scene.sog"
            target.write_bytes(b"existing")
            report = core.run_conversion(
                [core.Job(source, target)],
                core.Options(output_dir=root),
                "no-such-cli",
            )
            self.assertEqual(report.skipped, 1)
            self.assertIn("already exists", report.results[0].message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
