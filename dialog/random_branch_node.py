# pylint: disable=line-too-long, super-with-arguments

import copy

import numpy

from django.template import Template, Context

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

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments, too-many-locals
        choices = []
        weights = []

        weight_metadata = {}

        for action in self.random_actions:
            raw_weight = action['weight']

            value_template = Template(str(raw_weight))

            context_metadata = copy.deepcopy(dialog.metadata)

            if extras is not None:
                context_metadata.update(copy.deepcopy(extras))

            context = Context(context_metadata)

            rendered = value_template.render(context)

            weight = 1.0

            try:
                weight = float(rendered)
            except: # pylint: disable=bare-except
                weight = 1.0

            if weight > 0.0:
                choices.append(action['action'])
                weights.append(weight)

                weight_metadata[action['action']] = {
                    'raw_weight': raw_weight,
                    'rendered_weight': weight
                }

        chosen = None

        if len(choices) > 1:
            try:
                normalized_weights = numpy.array(weights) / numpy.sum(weights)
                chosen = numpy.random.choice(choices, p=normalized_weights)
            except ValueError:
                chosen = numpy.random.choice(choices)
        elif len(choices) == 1:
            chosen = choices[0]
        else:
            choices = []

            for action in self.random_actions:
                choices.append(action['action'])

            chosen = numpy.random.choice(choices)

        transition = DialogTransition(new_state_id=chosen)

        transition.metadata['reason'] = 'random-branch'
        transition.metadata['weights'] = weight_metadata

        return transition

    def actions(self):
        return []

    def next_nodes(self):
        nodes = []

        for action in self.random_actions:
            nodes.append((action['action'], 'Weight: ' + str(action['weight'])))

        return nodes
