#!/usr/bin/env python3
import ast
import glob
import os
import sys
from collections import defaultdict
from functools import lru_cache
from itertools import chain
from pathlib import Path

from colorama import init as colorama_init
from fixit.api import fixit_paths
from fixit.config import collect_rules, parse_rule
from fixit.ftypes import Config, Options

from oca_pre_commit_hooks import utils
from oca_pre_commit_hooks.base_checker import BaseChecker

colorama_init(autoreset=True)

DFTL_README_TMPL_URL = "https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst"  # noqa: B950
DFTL_README_FILES = ["README.md", "README.txt", "README.rst"]
DFTL_MANIFEST_DATA_KEYS = ["data", "demo", "demo_xml", "init_xml", "qweb", "test", "update_xml"]
MANIFEST_NAMES = ("__openerp__.py", "__manifest__.py")
MANIFEST_DATA_DIRS = [
    "data",
    "datas",
    "demo",
    "demos",
    "report",
    "reports",
    "security",
    "template",
    "templates",
    "view",
    "views",
    "wizard",
    "wizards",
]
MANIFEST_DATA_EXTS = [
    ".csv",
    ".xml",
]
DATA_MANUAL_KEY = "oca_data_manual"
BLUE_PILL = "\033[94m🔵\033[0m"
RED_PILL = "\033[91m🔴\033[0m"


class ChecksOdooModuleFixit(BaseChecker):
    def __init__(self, manifest_path, enable, disable, changed=None, verbose=True, autofix=False):
        super().__init__(enable, disable, autofix=autofix, module_version=utils.manifest_version(manifest_path))
        if not os.path.isfile(manifest_path) or os.path.basename(manifest_path) not in MANIFEST_NAMES:
            raise UserWarning(  # pragma: no cover
                f"Not valid manifest file name {manifest_path} file expected {MANIFEST_NAMES}"
            )
        self.manifest_path = manifest_path
        self.changed = changed if changed is not None else []
        self.verbose = verbose
        self.odoo_addon_path = os.path.dirname(self.manifest_path)
        self.manifest_top_path = utils.top_path(self.odoo_addon_path)
        self.odoo_addon_name = os.path.basename(self.odoo_addon_path)
        self.error = ""
        self.manifest_dict = self._manifest2dict()
        self.is_module_installable = self._is_installable()
        self.manifest_referenced_files = self._referenced_files_by_extension()
        self.checks_errors = []

    def _manifest2dict(self):
        if not os.path.isfile(os.path.join(self.odoo_addon_path, "__init__.py")):
            if self.verbose:
                print(f"[bold]{self.manifest_path}[/bold]: missing `__init__.py` file")
            return {}
        with open(self.manifest_path, encoding="UTF-8") as f_manifest:
            try:
                return ast.literal_eval(f_manifest.read())
            # Using same way than odoo
            except BaseException:  # pylint: disable=broad-except
                # Not use "exception error" string because it return mutable memory numbers
                self.error = "manifest malformed"
        return {}

    def _is_installable(self):
        return self.manifest_dict and self.manifest_dict.get("installable", True)

    def _glob_expr2filenames(self, data_section):
        """Support new way of odoo to add assets
        e.g. odoo/addons/spreadsheet_dashboard/__manifest__.py
        "assets": {
            "web.assets_backend": [
                "spreadsheet_dashboard/static/src/assets/**/*.js"

        It will return the following format:
            ['static/src/assets/path1/file1.js']
        Only if the module is the same
        """
        fnames = []
        data_section_value = self.manifest_dict.get(data_section)
        if isinstance(data_section_value, dict):
            fname_glob_lists = self.manifest_dict[data_section].values()
        elif isinstance(data_section_value, list):
            fname_glob_lists = [data_section_value]
        else:
            fname_glob_lists = []
        for fname_glob_list in fname_glob_lists:
            for fname_glob in fname_glob_list:
                if not isinstance(fname_glob, str):
                    continue
                if data_section == "qweb":
                    fname_glob = os.path.join(os.path.basename(self.odoo_addon_path), fname_glob)
                with utils.chdir(os.path.dirname(self.odoo_addon_path)):
                    for fname in glob.glob(fname_glob):
                        if not fname.startswith(self.odoo_addon_name):
                            continue
                        fname = os.path.relpath(fname, os.path.basename(self.odoo_addon_path))
                        fnames.append(fname)
        return fnames

    def _referenced_files_by_extension(self):
        ext_referenced_files = defaultdict(list)
        for data_section in DFTL_MANIFEST_DATA_KEYS + ["assets", "po"]:
            if data_section in ["assets", "qweb"]:
                # support glob expression
                manifest_fnames = self._glob_expr2filenames(data_section)
            elif data_section == "po":
                # The i18n[_extra]/*.po[t] files are not defined in the manifest
                manifest_fnames = glob.glob(os.path.join(self.odoo_addon_path, "i18n*", "*.po")) + glob.glob(
                    os.path.join(self.odoo_addon_path, "i18n*", "*.pot")
                )
            else:
                manifest_fnames = self.manifest_dict.get(data_section) or []
            for fname in manifest_fnames:
                fname_path = os.path.join(self.odoo_addon_path, fname)
                value = {
                    "filename": fname_path,
                    "filename_short": os.path.relpath(fname_path, self.manifest_top_path),
                    "data_section": data_section,
                }
                ext = os.path.splitext(fname)[1].lower()
                if value in ext_referenced_files[ext]:
                    # Duplicated files will be skipped in order to avoid detecting duplicated xmlids
                    # pylint will take care about this check error
                    continue
                ext_referenced_files[ext].append(value)
        return ext_referenced_files

    @staticmethod
    def _get_module_data_files(module_root_path):
        module_root_path_obj = Path(module_root_path).resolve()
        fnames = set()
        for subpath_obj in module_root_path_obj.rglob("*"):
            parts = subpath_obj.relative_to(module_root_path_obj).parts
            if (
                not subpath_obj.is_file()  # is file
                or len(parts) != 2  # only depth 2
                or parts[0].lower() not in MANIFEST_DATA_DIRS  # only valid dir
                or subpath_obj.suffix.lower() not in MANIFEST_DATA_EXTS  # only valid ext
            ):
                continue
            fnames.add(subpath_obj.relative_to(module_root_path_obj).as_posix())
        return fnames

    @staticmethod
    @lru_cache(maxsize=32)
    def _get_fixit_rules(manifest_rule):
        rule = parse_rule(".checks_odoo_module_fixit_rules", Path(os.path.dirname(os.path.abspath(__file__))))
        lint_rules = collect_rules(Config(enable=[rule], disable=[], python_version=None))
        return [
            (
                parse_rule(
                    f"{lint_rule.__module__.replace('fixit.local', '')}",
                    Path(os.path.dirname(os.path.abspath(__file__))),
                ),
                lint_rule.name,
            )
            for lint_rule in lint_rules
            if (
                manifest_rule
                and lint_rule.name.startswith("manifest-")
                or not manifest_rule
                and not lint_rule.name.startswith("manifest-")
            )
        ]

    def _get_fixit_enabled_rules(self, manifest_rule):
        lint_rules = self._get_fixit_rules(manifest_rule)
        return [lint_rule for lint_rule, lint_rule_name in lint_rules if self.is_message_enabled(lint_rule_name)]

    def _get_changed(self):
        """Return files to process if manifest is the unique file so it returns the directory of the module"""
        changed = set()
        for f_path in self.changed:
            curr_path = Path(f_path)
            changed |= {curr_path}
        manifest_path = Path(self.manifest_path)
        if changed == {manifest_path}:
            # Compatible with current way using only the manifest file for the whole module
            # TODO: Use file by file to use jobs in pre-commit
            changed = {manifest_path.parent}
        if {manifest_path.parent} & changed:
            # Manifest is not imported from __init__.py so it is included manually
            changed |= {manifest_path}
        return changed


    @utils.only_required_for_installable()
    def check_py_fixit(self):
        """Run fixit"""
        fixit_odoo_version = (
            os.environ.get("FIXIT_ODOO_VERSION")
            or self.module_version
            and str(self.module_version)
            or os.environ.get("VERSION")
            or "18.0"
        )
        with (
            utils.environ_tmp_set("FIXIT_ODOO_VERSION", fixit_odoo_version),
            utils.environ_tmp_set("FIXIT_AUTOFIX", str(self.autofix)),
        ):
            lint_rules_enabled_all = self._get_fixit_enabled_rules(manifest_rule=False)
            lint_rules_enabled_manifest = self._get_fixit_enabled_rules(manifest_rule=True)
            if not (lint_rules_enabled_all or lint_rules_enabled_manifest):
                return
            results = []
            changed = self._get_changed()
            manifest_path = Path(self.manifest_path)
            if lint_rules_enabled_manifest and {manifest_path} & changed:
                manifest_options = Options(debug=False, output_format="vscode", rules=lint_rules_enabled_manifest)
                results.append(
                    fixit_paths(
                        paths=[manifest_path],
                        options=manifest_options,
                        autofix=self.autofix,
                        parallel=False,
                    )
                )
            if lint_rules_enabled_all and self.changed:
                all_options = Options(debug=False, output_format="vscode", rules=lint_rules_enabled_all)
                results.append(
                    fixit_paths(
                        paths=changed,
                        options=all_options,
                        autofix=self.autofix,
                        parallel=False,
                    )
                )
            for result in chain.from_iterable(results):
                if not result.violation:
                    continue
                message = result.violation.message
                if result.violation.autofixable and not self.autofix:
                    message += " (has autofix)"
                filename_short = os.path.relpath(result.path.as_posix(), self.manifest_top_path)
                self.register_error(
                    code=result.violation.rule_name,
                    message=message,
                    info=(self.error or "")
                    + (
                        "You can disable this check by adding the following comment to the "
                        f"affected line or just above it `# lint-ignore: {result.violation.rule_name}`"
                    ),
                    filepath=filename_short,
                    line=result.violation.range.start.line,
                    column=result.violation.range.start.column,
                )

    @utils.only_required_for_installable()
    def check_py(self):
        """* Check use-header-comments
        Check if the py file has comments '# comment' only in the header of python files
        Except valid comments e.g. pylint, flake8, shebang or comments in the middle (not header)
        """
        if self.is_message_enabled("use-header-comments"):
            changed = self._get_changed()
            self._remove_header_comments(changed)

    def _get_files(self, directories_or_files, ext):
        new_files = set()
        for directory_or_file in directories_or_files:
            if directory_or_file.is_dir():
                new_files |= {f for f in directory_or_file.rglob(ext)}
            elif directory_or_file.is_file():
                new_files |= {directory_or_file}
        return new_files

    def _remove_header_comments(self, directories_or_files):
        for pyfile in self._get_files(directories_or_files, "*.py"):
            with pyfile.open("r") as f_py:
                content = ""
                needs_fix = False
                line_numbers_with_comment = []
                for no_line, line in enumerate(f_py, start=1):
                    line_strip = line.strip(" \n")
                    if not line_strip:
                        # empty line
                        content += line
                        continue
                    if line.startswith("#"):
                        if any(token in line for token in utils.VALID_HEADER_COMMENTS):
                            # valid comments
                            content += line
                            continue
                        # comment to remove
                        needs_fix = True
                        line_numbers_with_comment.append(no_line)
                    else:
                        content += line
                        break
                else:
                    continue  # The file contains only comments; skip to avoid deleting it
                if needs_fix:
                    fname_short = str(pyfile.relative_to(Path(self.manifest_top_path)))
                    self.register_error(
                        code="use-header-comments",
                        message=f"Use of header comments in lines {', '.join(map(str, line_numbers_with_comment))}",
                        info=self.error,
                        filepath=fname_short,
                        line=line_numbers_with_comment[-1],
                    )
                    if self.autofix:
                        content += "".join(line for line in f_py)
            if needs_fix and self.autofix:
                utils.perform_fix(str(pyfile), content.encode())


def lookup_manifest_paths(filenames_or_modules):
    """Look for manifest path for "filenames_or_modules" paths
    walking up in parent paths
    Return a dictionary with {manifest_path: filename_or_module} items
    """
    odoo_module_files_changed = defaultdict(set)
    # Sorted in order to re-use the LRU cached values as possible before to fill maxsize
    # Ordered paths will have common ancestors closed to next item
    for filename_or_module in sorted(filenames_or_modules):
        filename_or_module = utils.full_norm_path(filename_or_module)
        directory_path = (
            os.path.dirname(filename_or_module) if os.path.isfile(filename_or_module) else filename_or_module
        )
        manifest_path = utils.walk_up(directory_path, MANIFEST_NAMES, utils.top_path(directory_path))
        odoo_module_files_changed[manifest_path].add(filename_or_module)
    return odoo_module_files_changed


def run(files_or_modules, enable=None, disable=None, no_verbose=False, no_exit=False, list_msgs=False, autofix=False):
    if list_msgs:
        _, checks_docstring = utils.get_checks_docstring([ChecksOdooModuleFixit])
        if not no_verbose:
            print("Emittable messages with the current interpreter:", end="")
            print(checks_docstring)
        if no_exit:
            return checks_docstring
        sys.exit(0)

    all_check_errors = []
    # TODO: Add unnitest to check files filtered from pre-commit by hook
    # Uncommet to check what files sent pre-commit
    # open("/tmp/borrar.txt", "w").write(f"{len(files_or_modules)}\n{files_or_modules}")
    if enable is None:
        enable = set()
    if disable is None:
        disable = set()
    exit_status = 0
    for manifest_path, changed in lookup_manifest_paths(files_or_modules).items():
        if not manifest_path:
            continue
        checks_obj = ChecksOdooModuleFixit(
            os.path.realpath(manifest_path), enable, disable, changed=changed, verbose=not no_verbose, autofix=autofix
        )
        for check in utils.getattr_checks(checks_obj):
            check()
        if checks_obj.checks_errors:
            all_check_errors.extend(checks_obj.checks_errors)
            exit_status = 1
    # Sort errors by filepath, line, column and code
    all_check_errors.sort()
    # Print errors
    if not no_verbose:
        for error in all_check_errors:
            print(error)
            print("")
    if no_exit:
        return all_check_errors
    sys.exit(exit_status)


def main(**kwargs):
    return run(**kwargs)


if __name__ == "__main__":
    main()
