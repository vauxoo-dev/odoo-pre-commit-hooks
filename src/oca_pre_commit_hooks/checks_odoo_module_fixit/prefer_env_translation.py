import os
import warnings

import libcst as cst
from fixit import InvalidTestCase, LintRule, ValidTestCase
from libcst.metadata import QualifiedName, QualifiedNameProvider

ODOO_VERSION = os.getenv("FIXIT_ODOO_VERSION")


def version_parse(version_str):
    try:
        return tuple(map(int, version_str.split(".")))
    except (ValueError, TypeError):
        return tuple()


class PreferEnvTranslationRule(LintRule):
    """Replace _('text') with self.env._('text')
    only if '_' comes from 'odoo'."""

    MESSAGE = "Use self.env._(...) instead of _(…) directly inside Odoo model methods."
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)
    ODOO_MIN_VERSION = "18.0"
    VALID = []
    INVALID = []
    if version_parse(ODOO_MIN_VERSION) <= version_parse(ODOO_VERSION or "18.0"):
        VALID = [
            ValidTestCase(
                code="""
    from odoo import models, _


    class TestModel(models.Model):
        def my_method(self):
            self.env._("ok")
    """
            ),
            ValidTestCase(
                code="""
    from gettext import gettext as _


    def outside_model():
        _("not Odoo")
    """
            ),
            ValidTestCase(
                code="""
    _ = lambda *a: True


    class TestModel(models.Model):
        def my_method(self):
            _("is not a Odoo translation")
    """
            ),
        ]

        INVALID = [
            InvalidTestCase(
                code="""
    from odoo import models, _


    class TestModel(models.Model):
        def my_method(self):
            _("old translated")
    """,
                expected_replacement="""
    from odoo import models, _


    class TestModel(models.Model):
        def my_method(self):
            self.env._("old translated")
    """,
            ),
            InvalidTestCase(
                code="""
    from odoo import models, _ as lt


    class TestModel(models.Model):
        def my_method(self):
            lt("old translated")
    """,
                expected_replacement="""
    from odoo import models, _ as lt


    class TestModel(models.Model):
        def my_method(self):
            self.env._("old translated")
    """,
            ),
        ]

    def visit_Call(self, node: cst.Call) -> None:  # noqa: B906 pylint:disable=invalid-name
        odoo_version_tuple = version_parse(ODOO_VERSION)
        if not odoo_version_tuple:
            # TODO: R&D if there is a warning logger in the library
            warnings.warn(
                f"Invalid manifest versions format ({ODOO_VERSION}). "
                "It was not possible to run prefer_env_translation_rule",
                UserWarning,
                stacklevel=2,
            )
            return
        if not isinstance(node.func, cst.Name):
            return
        # TODO: R&D how to get the "version" from manifest of the current node's module
        if version_parse(self.ODOO_MIN_VERSION) > version_parse(ODOO_VERSION):
            return
        qualified_names = self.get_metadata(QualifiedNameProvider, node.func, set())
        for qname in qualified_names:
            if isinstance(qname, QualifiedName) and qname.name.startswith("odoo._"):
                self.report(node, replacement=self.fix(node))
                break

    def fix(self, node: cst.Call) -> cst.Call:
        return node.with_changes(
            func=cst.Attribute(
                value=cst.Attribute(
                    value=cst.Name("self"),
                    attr=cst.Name("env"),
                ),
                attr=cst.Name("_"),
            )
        )
