#!/usr/bin/env python3

# Hooks are using print directly
# pylint: disable=print-used

import os
import sys

DFTL_README_TMPL_URL = 'https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst'  # no-qa
DFTL_README_FILES = ['README.rst', 'README.md', 'README.txt']


def check_readme(manifest_path):
    for readme_name in DFTL_README_FILES:
        readme_path = os.path.join(os.path.dirname(manifest_path), readme_name)
        if os.path.isfile(readme_path):
            return True
    print("Missing %s file. Template here: %s" % (DFTL_README_FILES[0], DFTL_README_TMPL_URL))
    return False


def main():
    global_res = True
    for fname in sys.argv[1:]:
        res = check_readme(fname)
        if not res:
            global_res = False
    if not global_res:
        sys.exit(1)


if __name__ == "__main__":
    main()
