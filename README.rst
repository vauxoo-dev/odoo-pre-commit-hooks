========
Overview
========

OCA's custom pre-commit hooks


Installation
============

You don't need to install it directly only configure your ".pre-commit-config.yaml" file

Even you can install using github directly

    pip install -U git+https://github.com/OCA/odoo-pre-commit-hooks.git@master


Usage using pre-commit-config
=============================

Add to your ".pre-commit-config.yaml" configuration file the following input


.. code-block:: yaml

    - repo: https://github.com/OCA/odoo-pre-commit-hooks
        rev: master  # Change to last version or git sha
        hooks:
        - id: HOOK-NAME


Usage using directly the entry points
=====================================

If you install directly the package from github you can use the entry points:

    * HOOK-APP
