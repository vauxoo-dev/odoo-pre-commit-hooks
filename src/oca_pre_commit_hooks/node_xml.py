# Copyright 2023 Odoo Community Association (OCA)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import re

from lxml import etree


class NodeContent:
    def __init__(self, node, filename):
        self.node = node
        self.filename = filename
        self.start_sourceline = None
        self.end_sourceline = None
        self.content_node = None

    def _read_node(self):  # noqa:C901 pylint:disable=too-complex
        node_tag = self.node.tag.encode()

        if (node_previous := self.node.getprevious()) is not None:
            search_start_line = node_previous.sourceline + 1
        elif (node_parent := self.node.getparent()) is not None:
            search_start_line = node_parent.sourceline
        else:
            search_start_line = 2  # first element and it is the root

        search_end_line = (
            self.node.sourceline
            + len(etree.tostring(self.node).splitlines())
            + 2
        )

        with open(self.filename, "rb") as f_content:
            all_lines = list((i, line) for i, line in enumerate(f_content, start=1))

        search_start_line = min(search_start_line, search_end_line)

        # Find the actual node start by looking for the tag
        node_start_idx = None
        for idx, (no_line, line) in enumerate(all_lines):
            if search_start_line <= no_line <= search_end_line:
                stripped_line = line.lstrip()
                if b"<" + node_tag in stripped_line:
                    node_start_idx = idx
                    self.start_sourceline = no_line
                    break

        if node_start_idx is None:
            return

        # Find the actual node end
        for idx, (no_line, line) in enumerate(
            all_lines[node_start_idx:], start=node_start_idx
        ):
            stripped_line = line.lstrip()

            if stripped_line.startswith(b"</" + node_tag):
                node_end_idx = idx
                self.end_sourceline = no_line
                break

            # Self-closing continuation
            if re.search(rb"/>\s*$", stripped_line):
                node_end_idx = idx
                self.end_sourceline = no_line
                break

        else:
            return

        self.content_node = "".join(
            line for _, line in all_lines[node_start_idx : node_end_idx + 1]
        )

    def read(self):
        self._read_node()
        return self