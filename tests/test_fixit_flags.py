import os
import shutil
import tempfile
from pathlib import Path

import pytest

import oca_pre_commit_hooks.checks_odoo_module_fixit
from . import common

MANIFEST_ONLY_CODES = {"manifest-superfluous-key": 2}
WHOLE_MODULE_CODES = {
    "manifest-superfluous-key": 2,
    "field-string-redundant": 30,
    "prefer-env-translation": 39,
    "unused-logger": 1,
}


class TestFixitFlags:
    @classmethod
    def setup_class(cls):
        cls.original_test_repo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "test_repo"
        )

    def setup_method(self, method):
        self.tmp_dir = os.path.realpath(tempfile.mkdtemp(suffix="_oca_pre_commit_hooks"))
        common.create_dummy_repo(self.original_test_repo_path, self.tmp_dir)
        self.manifest_path = os.path.join(self.tmp_dir, "broken_module", "__openerp__.py")

    def teardown_method(self, method):
        if os.path.isdir(self.tmp_dir) and self.tmp_dir != "/":
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @staticmethod
    def get_count_code_errors(all_check_errors):
        return common.ChecksCommon.get_count_code_errors(all_check_errors)

    def test_manifest_expands_to_whole_module_by_default(self):
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module_fixit.run(
            [self.manifest_path], no_exit=True, no_verbose=True
        )
        assert self.get_count_code_errors(all_check_errors) == WHOLE_MODULE_CODES

    def test_standalone_parallel_matches_precommit_serial(self):
        """Without PRE_COMMIT in the environment the modules are processed by a process
        pool and must report the same errors as the serial pre-commit path"""
        manifest_paths = [self.manifest_path, os.path.join(self.tmp_dir, "eleven_module", "__manifest__.py")]
        expected_errors = dict(WHOLE_MODULE_CODES, **{"use-header-comments": 1})
        serial_errors = oca_pre_commit_hooks.checks_odoo_module_fixit.run(
            manifest_paths, no_exit=True, no_verbose=True
        )
        assert self.get_count_code_errors(serial_errors) == expected_errors
        mp = pytest.MonkeyPatch()
        mp.delenv("PRE_COMMIT", raising=False)
        try:
            parallel_errors = oca_pre_commit_hooks.checks_odoo_module_fixit.run(
                manifest_paths, no_exit=True, no_verbose=True
            )
        finally:
            mp.undo()
        assert sorted(parallel_errors) == sorted(serial_errors)

    def test_no_expand_manifest_checks_only_the_manifest(self):
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module_fixit.run(
            [self.manifest_path], no_exit=True, no_verbose=True, no_expand_manifest=True
        )
        assert self.get_count_code_errors(all_check_errors) == MANIFEST_ONLY_CODES

    def test_no_expand_manifest_with_sibling_files(self):
        """When more files than the manifest are passed only those files are checked, same as before"""
        model_path = os.path.join(self.tmp_dir, "broken_module", "models", "broken_model.py")
        all_check_errors = oca_pre_commit_hooks.checks_odoo_module_fixit.run(
            [self.manifest_path, model_path], no_exit=True, no_verbose=True, no_expand_manifest=True
        )
        codes = self.get_count_code_errors(all_check_errors)
        assert codes["manifest-superfluous-key"] == MANIFEST_ONLY_CODES["manifest-superfluous-key"]
        assert set(codes) - {"manifest-superfluous-key"}, "Expected file-level errors from the sibling file"

    def test_autofix_applies_fixes(self):
        original_contents = {
            py_file: py_file.read_bytes() for py_file in (Path(self.tmp_dir) / "broken_module").rglob("*.py")
        }
        errors_autofix = oca_pre_commit_hooks.checks_odoo_module_fixit.run(
            [self.manifest_path], no_exit=True, no_verbose=True, autofix=True
        )
        assert self.get_count_code_errors(errors_autofix) == WHOLE_MODULE_CODES
        assert any(
            py_file.read_bytes() != content for py_file, content in original_contents.items()
        ), "Autofix did not modify any file"
        errors_after = oca_pre_commit_hooks.checks_odoo_module_fixit.run(
            [self.manifest_path], no_exit=True, no_verbose=True
        )
        remaining = self.get_count_code_errors(errors_after)
        assert set(remaining) < set(WHOLE_MODULE_CODES), f"Autofixable errors still present: {remaining}"
