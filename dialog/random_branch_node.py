# pylint: disable=line-too-long, super-with-arguments

from builtins import str # pylint: disable=redefined-builtin

import copy
import json

import numpy

from django.template import Template, Context

from .base_node import BaseNode
from .dialog_machine import DialogTransition

class RandomBranchNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'random-branch':
            branch_node = RandomBranchNode(dialog_def['id'], dialog_def['actions'], dialog_def.get('without_replacement', False))

            return branch_node

        return None

    def __init__(self, node_id, actions, without_replacement=False):
        super(RandomBranchNode, self).__init__(node_id, node_id)

        if actions is None:
            self.random_actions = []
        else:
            self.random_actions = actions

        self.without_replacement = without_replacement

    def node_type(self):
        return 'random-branch'

    def prefix_nodes(self, prefix):
        super().prefix_nodes(prefix) # pylint: disable=missing-super-argument

        for action in self.random_actions:
            action['action'] = prefix + action['action']

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        if 'next_id' in node_def:
            del node_def['next_id']

        node_def['actions'] = self.random_actions
        node_def['without_replacement'] = self.without_replacement

        return node_def

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments, too-many-locals, too-many-branches, too-many-statements
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

        if self.without_replacement and extras is not None:
            key = '__%s_prior_choices' % self.node_id

            if (key in extras) is False:
                extras[key] = []

            for prior_choice in extras[key]:
                try:
                    index = choices.index(prior_choice)

                    choices.pop(index)
                    weights.pop(index)

                    del weight_metadata[prior_choice]

                except ValueError:
                    pass # Not in list

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

        if self.without_replacement and extras is not None:
            key = '__%s_prior_choices' % self.node_id

            if extras.get(key, None) is None:
                extras[key] = []

            if isinstance(extras[key], str):
                extras[key] = json.loads(extras[key])

            if len(choices) > 1:
                extras[key].append(chosen)
            else:
                extras[key] = []

            transition.metadata['prior_choices'] = extras[key]

            transition.metadata['exit_actions'] = [{
                'type': 'store-value',
                'key': key,
                'value': json.dumps(extras[key])
            }]

        return transition

    def actions(self):
        return []

    def next_nodes(self):
        nodes = []

        for action in self.random_actions:
            nodes.append((action['action'], 'Weight: ' + str(action['weight'])))

        return nodes
