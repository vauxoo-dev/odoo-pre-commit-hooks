import os
import tempfile
import unittest

from oca_pre_commit_hooks.checks_odoo_module_xml import ChecksOdooModuleXML


class TestClassCheckers(unittest.TestCase):

    def test_enabled_checks(self):
        """Ensure all checks are enabled by default"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = os.path.join(tmp_dir, "__manifest__.py")
            with open(manifest_path, 'w') as manifest:
                manifest.write("not important")

            xml_checker = ChecksOdooModuleXML()
            self.assertEqual(xml_checker.get_all_messages(), xml_checker.get_active_messages())
