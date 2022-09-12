#!/usr/bin/env python3

# Hooks are using print directly
# pylint: disable=print-used

import ast
import os
import sys

DFTL_README_TMPL_URL = 'https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst'  # no-qa
DFTL_README_FILES = ['README.rst', 'README.md', 'README.txt']


class ChecksOdooModule(object):
    def __init__(self, manifest_path):
        self.manifest_path = os.path.relpath(manifest_path)
        self.odoo_addon_path = os.path.dirname(self.manifest_path)
        self._get_manifest_content()
        self.readme_path = None

    def _get_manifest_content(self):
        if not os.path.isfile(os.path.join(self.odoo_addon_path, "__init__.py")):
            return
        with open(self.manifest_path) as f_manifest:
            self.manifest_content = ast.literal_eval(f_manifest.read())
    
    def _is_module_installable(self):
        return self.manifest_content and self.manifest_content.get('installable', True)

    def check(self, name):
        check_method = getattr(self, "check_%s" % name, None)
        if not callable(check_method) or check_method.startswith("_"):
            print("Check %s is not callable or is calling private method" % name)
            return
        if not self._is_module_installable():
            return True
        return check_method()

    def check_missing_readme(self):
        for readme_name in DFTL_README_FILES:
            readme_path = os.path.join(self.odoo_addon_path, readme_name)
            if os.path.isfile(readme_path):
                self.readme_path = readme_path()
                return True
        print("Missing %s file. Template here: %s" % (DFTL_README_FILES[0], DFTL_README_TMPL_URL))
        return False


def main_missing_readme():
    global_res = True
    for fname in sys.argv[1:]:
        obj = ChecksOdooModule(fname)
        res = obj.check("missing_readme")
        if not res:
            global_res = False
    if not global_res:
        sys.exit(1)


def main():
    main_missing_readme()


if __name__ == "__main__":
    main()
