"""Tests for .tau/taukey.py path resolution and loader behavior.

These tests redirect TAU_HOME to a tmp dir so they don't read the
real user config, and they don't depend on the user having a real
.tau/taukey.py installed.
"""
import os, sys, tempfile, textwrap, unittest
from pathlib import Path
from unittest import mock


class TestTaukeyPath(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        (self.tmp / ".tau").mkdir()
        # Start the env patcher (NOT inside a `with` block — we need it
        # to persist into the test methods). Stop it in addCleanup so it
        # is restored between tests.
        env = {**os.environ, "TAU_HOME": str(self.tmp)}
        self._env_patcher = mock.patch.dict(os.environ, env, clear=True)
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)
        # Reload core.paths and core.llm.keys with TAU_HOME=tmp.
        for mod in list(sys.modules):
            if mod == "core.paths" or mod.startswith("core.llm.keys"):
                del sys.modules[mod]
        from core.paths import TAU, TAUKEY_PATH  # noqa
        from core.llm.keys import _load_taukeys, reload_taukeys  # noqa
        self.TAU = TAU
        self.TAUKEY_PATH = TAUKEY_PATH
        self._load = _load_taukeys
        self._reload = reload_taukeys

        # The legacy JSON fallback in core/llm/keys.py reads
        # core/llm/taukey.json from the loader's own __file__ directory,
        # NOT from TAU_HOME. To exercise the "missing file" branch of
        # the loader, we must hide this file for the duration of each test.
        import shutil
        self._legacy_json = Path(__file__).resolve().parent.parent / "core" / "llm" / "taukey.json"
        self._legacy_json_backup = None
        if self._legacy_json.exists():
            self._legacy_json_backup = self._legacy_json.with_suffix(".json.test_bak")
            shutil.move(str(self._legacy_json), str(self._legacy_json_backup))

        def _restore_legacy_json():
            if self._legacy_json_backup and self._legacy_json_backup.exists():
                shutil.move(str(self._legacy_json_backup), str(self._legacy_json))
        self.addCleanup(_restore_legacy_json)

    def test_path_constants_resolve_under_tau_home(self):
        self.assertEqual(self.TAU, Path(os.environ["TAU_HOME"]) / ".tau")
        self.assertEqual(self.TAUKEY_PATH, self.TAU / "taukey.py")

    def test_missing_raises_with_new_path_and_hint(self):
        with self.assertRaises(Exception) as ctx:
            self._load()
        msg = str(ctx.exception)
        self.assertIn(str(self.TAUKEY_PATH), msg)
        self.assertIn("tau configure", msg)

    def test_loads_module_vars_filters_underscore(self):
        self.TAUKEY_PATH.write_text(textwrap.dedent("""\
            _SETUP_DONE = 'configure.py'
            mixin_config = {'llm_nos': ['a']}
            cfg_a = {'apikey': 'k', 'apibase': 'x', 'model': 'm'}
        """), encoding="utf-8")
        d = self._load()
        self.assertEqual(set(d), {"mixin_config", "cfg_a"})
        self.assertEqual(d["cfg_a"]["apikey"], "k")
        self.assertEqual(d["mixin_config"]["llm_nos"], ["a"])

    def test_root_level_taukey_py_is_silently_ignored(self):
        # Place a sentinel file at TAU_HOME/taukey.py — this mimics the
        # OLD location (repo root) being readable via `import taukey`.
        # The new loader must NOT pick it up; it only reads .tau/taukey.py.
        (Path(os.environ["TAU_HOME"]) / "taukey.py").write_text(
            "legacy = {'sentinel': 'root'}\n", encoding="utf-8"
        )
        # .tau/taukey.py does NOT exist → must raise, not return legacy dict.
        with self.assertRaises(Exception):
            self._load()


if __name__ == "__main__":
    unittest.main()
