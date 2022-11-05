import os
import tempfile
import unittest

from oca_pre_commit_hooks.checks_odoo_module_xml import ChecksOdooModuleXML


class TestClassCheckers(unittest.TestCase):

    def test_enabled_checks(self):
        """Ensure all messages (and therefore checks) are enabled by default.
        """
        xml_checker = ChecksOdooModuleXML([], [])
        self.assertEqual(xml_checker.get_all_messages(), xml_checker.get_active_messages())
