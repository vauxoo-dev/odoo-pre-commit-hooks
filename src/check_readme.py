#!/usr/bin/env python3

# Hooks are using print directly
# pylint: disable=print-used

import json
import re
import sys

from jinja2 import Template


def check_readme(manifest_path):
    readme_path = os.path.join(os.path.dirname(manifest_path), "README.rst")
    if not os.path.isfile(readme_path):
        return False
    return True


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
