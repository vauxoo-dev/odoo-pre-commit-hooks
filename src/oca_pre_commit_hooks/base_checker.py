from typing import Set


class BaseChecker:

    def __init__(self, enable: Set, disable: Set, config):
        self.enable = enable
        self.disable = disable
        self.config = config
