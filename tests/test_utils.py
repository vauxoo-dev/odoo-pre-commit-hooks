import os
from pathlib import Path
from tempfile import TemporaryDirectory

from oca_pre_commit_hooks import utils
from oca_pre_commit_hooks.checks_odoo_module_fixit import MANIFEST_NAMES


class TestUtils:
    def test_top_path(self):
        """Test the top level path is inferred from the first parent path containing a ".git" entry"""
        with TemporaryDirectory() as tmp_dir:
            tmp_dir = os.path.realpath(tmp_dir)
            repo_path = os.path.join(tmp_dir, "repo")
            module_path = os.path.join(repo_path, "module", "models")
            os.makedirs(module_path)
            os.makedirs(os.path.join(repo_path, ".git"))
            assert utils.top_path(module_path) == repo_path
            assert utils.top_path(repo_path) == repo_path
            # A child of a top level path already found re-uses it directly
            # based on the path prefix without checking ".git" again
            nested_repo_path = os.path.join(module_path, "nested_repo")
            os.makedirs(os.path.join(nested_repo_path, ".git"))
            assert utils.top_path(nested_repo_path) == repo_path
            # Without a .git parent path the top is the root or the user's HOME
            no_repo_path = os.path.join(tmp_dir, "no_repo")
            os.makedirs(no_repo_path)
            assert utils.top_path(no_repo_path) == (Path(no_repo_path).root or str(Path.home()))

    def test_walk_up(self):
        """Test the manifest is found walking up limited by the top path"""
        with TemporaryDirectory() as tmp_dir:
            tmp_dir = os.path.realpath(tmp_dir)
            repo_path = os.path.join(tmp_dir, "repo")
            module_path = os.path.join(repo_path, "module")
            models_path = os.path.join(module_path, "models")
            os.makedirs(models_path)
            os.makedirs(os.path.join(repo_path, ".git"))
            manifest_path = os.path.join(module_path, "__manifest__.py")
            with open(manifest_path, "w", encoding="utf-8") as f_manifest:
                f_manifest.write("{}")
            top = utils.top_path(models_path)
            assert top == repo_path
            assert utils.walk_up(models_path, MANIFEST_NAMES, top) == manifest_path
            # A child of a parent path where the manifest was already found
            # re-uses it directly without checking the filesystem again
            wizards_path = os.path.join(module_path, "wizards")
            os.makedirs(wizards_path)
            assert utils.walk_up(wizards_path, MANIFEST_NAMES, top) == manifest_path
            # No manifest between the path and the top
            other_path = os.path.join(repo_path, "other")
            os.makedirs(other_path)
            assert utils.walk_up(other_path, MANIFEST_NAMES, top) is None
