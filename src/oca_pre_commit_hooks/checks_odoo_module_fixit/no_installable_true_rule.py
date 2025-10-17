import libcst as cst
from fixit import InvalidTestCase, LintRule, ValidTestCase


class NoInstallableTrueRule(LintRule):
    """Identifies and removes 'installable': True from Odoo manifest files (__manifest__.py).
    'installable': True is the default and should be omitted for simplicity.
    Same for other default values
    """
    INVALID = [
        InvalidTestCase(
            code="""
{
    'installable': True,
    'depends': [],
    'author': '',
    'name': 'My Module',
}
    """,
            expected_replacement="""
{
    'name': 'My Module',
}
    """,
        ),
        InvalidTestCase(
            code="""
{
    'installable': True,
    'name': 'Another Module',
}
    """,
            expected_replacement="""
{
    'name': 'Another Module',
}
    """,
        ),
        InvalidTestCase(
            code="""
{
    "active": True,
    "installable": (
        True),
    "name": "hello",
}
    """,
            expected_replacement="""
{
    "name": "hello",
}
    """,
        ),
    ]

    VALID = [
        ValidTestCase(
            code="""
    {
        'name': 'My Module',
        'depends': ['base'],
        'installable': False,
        'active': False,
    }
    """
        ),
        ValidTestCase(
            code="""
    {
        'name': 'My Module',
        'depends': ['base'],
    }
    """
        ),
    ]

    def visit_DictElement(self, node: cst.DictElement) -> None:  # pylint:disable=invalid-name
        if not isinstance(node.key, cst.SimpleString):
            return
        if (isinstance(node.value, cst.List) and not node.value.elements) or (
            isinstance(node.value, cst.SimpleString) and not node.value.evaluated_value
        ):
            self.report(
                node,
                "Delete empty values.",
                replacement=cst.RemoveFromParent(),
            )
        if (
            node.key.evaluated_value in ("active", "installable")
            and isinstance(node.value, cst.Name)
            and node.value.value == "True"
        ):
            self.report(
                node,
                "Delete default values",
                replacement=cst.RemoveFromParent(),
            )
