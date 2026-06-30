import os, importlib, unittest
from pathlib import Path

class TestCorePaths(unittest.TestCase):
    def test_constants_point_to_existing_repo_dirs(self):
        from core import paths
        self.assertTrue(paths.ASSETS.is_dir())
        self.assertTrue(paths.MEMORY.is_dir())
        self.assertEqual(paths.ASSETS, paths.TAU_HOME / "assets")
        self.assertEqual(paths.MEMORY, paths.TAU_HOME / "memory")

    def test_tau_home_env_override(self):
        os.environ["TAU_HOME"] = "/tmp/tau_home_probe"
        from core import paths
        importlib.reload(paths)
        self.assertEqual(paths.TAU_HOME, Path("/tmp/tau_home_probe"))
        del os.environ["TAU_HOME"]
        importlib.reload(paths)
