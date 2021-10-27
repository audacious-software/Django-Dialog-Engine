# pylint: disable=line-too-long, super-with-arguments

import numpy

from .base_node import BaseNode
from .dialog_machine import DialogTransition

class RandomBranchNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'random-branch':
            branch_node = RandomBranchNode(dialog_def['id'], dialog_def['actions'])

            return branch_node

        return None

    def __init__(self, node_id, actions):
        super(RandomBranchNode, self).__init__(node_id, node_id)

        if actions is None:
            self.random_actions = []
        else:
            self.random_actions = actions

    def node_type(self):
        return 'random-branch'

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        choices = []
        weights = []

        for action in self.random_actions:
            choices.append(action['action'])
            weights.append(action['weight'])

        chosen = None

        try:
            chosen = numpy.random.choice(choices, p=weights)
        except ValueError:
            chosen = numpy.random.choice(choices)

        transition = DialogTransition(new_state_id=chosen)

        transition.metadata['reason'] = 'random-branch'

        return transition

    def actions(self):
        return []

    def next_nodes(self):
        nodes = []

        for action in self.random_actions:
            nodes.append((action['action'], 'Weight: ' + str(action['weight'])))

        return nodes
