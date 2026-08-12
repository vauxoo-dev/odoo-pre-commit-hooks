import os
import re
import shutil
import subprocess
import sys
import tempfile
from ast import literal_eval
from contextlib import contextmanager
from functools import lru_cache
from inspect import getmembers, isfunction
from itertools import chain
from pathlib import Path

from packaging.version import InvalidVersion, Version

from oca_pre_commit_hooks.base_checker import BaseChecker

CHECKS_DISABLED_REGEX = re.compile(re.escape("oca-hooks:disable=") + r"([a-z\-,]+)")
DEPRECATED_CHECKS_DISABLED_REGEX = re.compile(re.escape("pylint:disable=") + r"([a-z\-,]+)")
RE_CHECK_DOCSTRING = r"\* Check (?P<check>[\w|\-]+)"
DFLT_BOOLEAN_FIELDS = [
    # common boolean fields repeated for many models
    "active",
    "is_published",
    "website_published",
]
DFLT_BOOLEAN_FIELDS_BY_MODEL = {
    "account.payment.term": [
        "is_fixed",
    ],
    "account.report": [
        "filter_journals",
        "filter_unfold_all",
    ],
    "account.report.column": [
        "sortable",
    ],
    "account.report.expression": [
        "auditable",
        "green_on_positive",
    ],
    "account.report.line": [
        "foldable",
        "hide_if_zero",
        "hierarchy_level",
    ],
    "hr.payslip.input.type": [
        "available_in_attachments",
    ],
    "hr.salary.rule": [
        "appears_on_payroll_report",
        "appears_on_payslip",
    ],
    "hr.work.entry.type": [
        "is_leave",
    ],
    "ir.attachment": [
        "public",
    ],
    "ir.rule": [
        "perm_create",
        "perm_read",
        "perm_unlink",
        "perm_write",
    ],
    "mail.message.subtype": [
        "default",
    ],
    "mail.template": [
        "auto_delete",
    ],
    "payment.method": [
        "support_express_checkout",
        "support_tokenization",
    ],
    "planning.slot": [
        "publication_warning",
    ],
    "product.product": [
        "available_in_pos",
    ],
    "product.template": [
        "available_in_pos",
    ],
    "res.partner": [
        "is_company",
    ],
}
DFLT_NUMERIC_FIELDS = [
    # common numeric fields repeated for many models
    "color",
    "sequence",
    "website_sequence",
]
DFLT_NUMERIC_FIELDS_BY_MODEL = {
    "account.analytic.line": [
        "amount",
        "unit_amount",
    ],
    "ir.cron": [
        "interval_number",
        "numbercall",
    ],
    "ir.ui.view": [
        "priority",
    ],
    "product.product": [
        "list_price",
        "standard_price",
        "weight",
    ],
    "product.template": [
        "list_price",
        "standard_price",
        "weight",
    ],
    "res.currency": [
        "rounding",
    ],
    "res.currency.rate": [
        "rate",
    ],
    "sale.order.line": [
        "price_unit",
        "product_uom_qty",
    ],
    "stock.move": [
        "product_uom_qty",
        "quantity_done",
    ],
}


def checks_disabled(comment):
    comment_strip = comment.replace("\n", "").replace(" ", "").replace("#", "")
    check_disable_match = CHECKS_DISABLED_REGEX.search(comment_strip)
    check_deprecated_disable_match = DEPRECATED_CHECKS_DISABLED_REGEX.search(comment_strip)

    match = check_disable_match or check_deprecated_disable_match
    use_deprecate = bool(check_deprecated_disable_match)
    if not match:
        return [], False

    return match.groups()[0].split(","), use_deprecate


def only_required_for_checks(*checks):
    """Decorator to store checks that are handled by a checker method as an
    attribute of the function object.

    This information is used to decide whether to call the decorated
    method or not. If none of the checks is enabled, the method will be skipped.
    """

    def store_checks(func):
        setattr(func, "checks", set(checks))  # noqa: B010
        return func

    return store_checks


def only_required_for_installable():
    """Decorator to store checks that are handled by a checker method as an
    attribute of the function object.

    This information is used to decide whether to call the decorated
    method or not. If the module is not installabe, the method will be skipped.
    """

    def store_installable(func):
        setattr(func, "installable", True)  # noqa: B010
        return func

    return store_installable


def getattr_checks(obj_or_class: BaseChecker, prefix="check_", disable_node=None):
    """Get all the attributes callables (methods)
    that start with word 'def check_*'
    Skip the methods with attribute "checks" defined if
    the check is not enable or if it is disabled"""
    for attr in dir(obj_or_class):
        if not callable(getattr(obj_or_class, attr)) or not attr.startswith(prefix):
            continue
        meth = getattr(obj_or_class, attr)
        meth_checks = getattr(meth, "checks", set())
        if meth_checks and not any(
            obj_or_class.is_message_enabled(meth_check, disable_node) for meth_check in meth_checks
        ):
            continue
        meth_installable = getattr(meth, "installable", None)
        is_module_installable = getattr(obj_or_class, "is_module_installable", None)
        if (
            meth_installable is not None
            and is_module_installable is not None
            and meth_installable
            and not is_module_installable
        ):
            continue
        yield getattr(obj_or_class, attr)


@contextmanager
def chdir(directory):
    """Change the current directory similar to command 'cd directory'
    but remembering the previous value to be revert at final
    Similar to run 'original_dir=$(pwd) && cd odoo && cd ${original_dir}'
    """
    original_dir = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(original_dir)


# Cache of the top level path resolved for each path already visited and
# set of the top level paths already found containing a ".git" entry
_top_path_cache = {}
_known_top_paths = set()


def top_path(path):
    """Get the top level path based on the first parent path containing a ".git"
    entry (a directory for regular repositories or a file for submodules and worktrees)
    If no git repository is found (and therefore no top level path), the user's HOME is returned.

    It looks for the ".git" entry instead of running "git rev-parse --show-toplevel"
    since that spawning a subprocess per directory was a significant slice of the
    whole runtime (py-spy profiled)

    The values are cached and the children paths of a top level path already found
    re-use it directly based on the path prefix so they are resolved without
    checking ".git" for each parent path again

    Notice it is not compatible with TemporaryDirectory since that it needs to have a .git folder
    but you can fix it using "git init"
    """
    path = str(path)
    top = _top_path_cache.get(path)
    if top is not None:
        return top
    path_obj = full_norm_path_obj(path)
    for known_top_path in _known_top_paths:
        if path_obj.is_relative_to(known_top_path):
            _top_path_cache[path] = known_top_path
            return known_top_path
    if (path_obj / ".git").exists():
        # Native separators (not "as_posix()") to match the rest of the codebase,
        # which builds and compares paths with "os.path" using the OS separator
        top = str(path_obj)
        _known_top_paths.add(top)
    else:
        parent_path = path_obj.parent
        if parent_path == path_obj:
            top = path_obj.root or str(Path.home())
        else:
            top = top_path(str(parent_path))
    _top_path_cache[path] = top
    return top


@lru_cache(maxsize=64)
def repo_name(path):
    """Get the repository name based on the first git remote URL."""
    try:
        # Get the list of remotes
        remotes = (
            subprocess.check_output(["git", "-C", path, "remote"], stderr=subprocess.STDOUT)
            .decode(sys.stdout.encoding)
            .splitlines()
        )
        # Get the URL of the remote
        remote_url = (
            subprocess.check_output(["git", "-C", path, "remote", "get-url", remotes[0]], stderr=subprocess.STDOUT)
            .decode(sys.stdout.encoding)
            .strip()
        )
        # Get the repo name
        repo = os.path.splitext(os.path.basename(remote_url.rstrip("/")))[0]
        return repo
    except (FileNotFoundError, subprocess.CalledProcessError, IndexError):
        return ""


def full_norm_path_obj(path):
    """Expand paths in all possible ways returning a "Path" object
    "Path.resolve()" replaces the previous abspath + realpath + normpath chain in a
    single call since it already returns an absolute path resolving the symlinks and
    normalizing the parent references ("os.path.expandvars" is kept because pathlib
    does not provide an equivalent)
    """
    return Path(os.path.expandvars(str(path).strip())).expanduser().resolve()


def full_norm_path(path):
    """Expand paths in all possible ways"""
    return str(full_norm_path_obj(path))


# Cache of the results already resolved by path, filenames and top and the
# parent paths where one of the filenames was already found by filenames
_walk_up_cache = {}
_known_walk_up_dirs = {}


def walk_up(path, filenames, top):
    """Look for "filenames" walking up in parent paths of "path"
    but limited only to "top" path
    The results are cached and the children paths of a parent path where one of
    the filenames was already found re-use it directly without checking the
    filesystem for each parent path again
    """
    cache_key = (path, filenames, top)
    try:
        return _walk_up_cache[cache_key]
    except KeyError:
        pass
    known_dirs = _known_walk_up_dirs.setdefault(filenames, {})
    path_obj = Path(path)
    result = None
    for parent_path in (path_obj, *path_obj.parents):
        result = known_dirs.get((str(parent_path), top))
        if result is not None:
            break
    if result is None:
        top_norm_path = full_norm_path_obj(top)
        current_path = path_obj
        while full_norm_path_obj(current_path) != top_norm_path:
            for filename in filenames:
                path_filename = current_path / filename
                if full_norm_path_obj(path_filename).is_file():
                    result = str(path_filename)
                    known_dirs[(str(current_path), top)] = result
                    break
            if result is not None or current_path.parent == current_path:
                break
            current_path = current_path.parent
    _walk_up_cache[cache_key] = result
    return result


def get_checks_docstring(check_classes):
    checks_docstring = ""
    checks_found = set()
    for check_class in check_classes:
        check_meths = chain(
            [member[1] for member in getmembers(check_class, predicate=isfunction) if member[0].startswith("check")],
            [member[1] for member in getmembers(check_class, predicate=isfunction) if member[0].startswith("visit")],
        )
        # Sorted to avoid mutable checks order readme
        check_meths = sorted(
            list(check_meths), key=lambda m: m.__name__.replace("visit", "", 1).replace("check", "", 1).strip("_")
        )
        for check_meth in check_meths:
            if not check_meth or not check_meth.__doc__ or "* Check" not in check_meth.__doc__:
                continue
            checks_docstring += "\n" + check_meth.__doc__.strip(" \n") + "\n"
            checks_found |= set(re.findall(RE_CHECK_DOCSTRING, checks_docstring))
            checks_docstring = re.sub(r"( )+\*", "*", checks_docstring)
    return checks_found, checks_docstring


def str2version(version_str):
    try:
        return Version(version_str)
    except (InvalidVersion, TypeError):
        return None


def manifest_version(manifest_path):
    with open(manifest_path, encoding="utf-8") as manifest_fd:
        try:
            manifest = literal_eval(manifest_fd.read())
        except (ValueError, SyntaxError):
            return None
    return str2version(manifest.get("version"))


def perform_fix(file_path, new_content):
    """Perform the fix by overwriting the file with the new content
    using a temp file to copy after."""
    # Use `delete=False` to be able to copy the file on Windows
    with tempfile.NamedTemporaryFile("wb", delete=False) as f_tmp:
        f_tmp.write(new_content)
    shutil.copy(f_tmp.name, file_path)
    os.unlink(f_tmp.name)


@contextmanager
def environ_tmp_set(key, value):
    old_value = os.environ.get(key)
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value
    try:
        yield
    finally:
        if old_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old_value
