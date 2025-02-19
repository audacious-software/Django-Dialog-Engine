# pylint: disable=line-too-long, super-with-arguments

import re

from .base_node import BaseNode, DialogTransition

class InterruptNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'interrupt':
            interrupt_node = InterruptNode(dialog_def['id'], dialog_def['match_patterns'], dialog_def['next_id'])

            return interrupt_node

        return None

    def __init__(self, node_id, match_patterns, next_node_id):
        super(InterruptNode, self).__init__(node_id, next_node_id)

        if match_patterns is None:
            self.match_patterns = []
        else:
            self.match_patterns = match_patterns

    def node_type(self):
        return 'interrupt'

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        node_def['match_patterns'] = self.match_patterns

        return node_def

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        dialog.push_value('django_dialog_engine_interrupt_node_stack', last_transition.prior_state_id)

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'interrupt-continue'

        return transition

    def actions(self):
        return []

    def matches(self, response):
        if response is None:
            return None

        for match_pattern in self.match_patterns:
            if re.search(match_pattern, response, re.IGNORECASE) is not None:
                return match_pattern

        return None

    def search_text(self):
        values = ['interrupt']

        for match_pattern in self.match_patterns:
            values.append(match_pattern)

        if self.next_node_id is not None:
            values.append(self.next_node_id)

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
