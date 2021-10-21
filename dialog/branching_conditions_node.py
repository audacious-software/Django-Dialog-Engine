# pylint: disable=line-too-long, super-with-arguments

import traceback

from django.utils.encoding import smart_str

from .base_node import BaseNode, fetch_default_logger
from .dialog_machine import DialogTransition

class BranchingConditionsNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'branch-conditions':
            branch_node = BranchingConditionsNode(dialog_def['id'], dialog_def['actions'])

            if 'no_match' in dialog_def:
                branch_node.no_match_node_id = dialog_def['no_match']

            if 'error' in dialog_def:
                branch_node.error_node = dialog_def['error']

            return branch_node

        return None

    def __init__(self, node_id, actions, no_match_node_id=None, error_node=None):
        super(BranchingConditionsNode, self).__init__(node_id, node_id)

        self.no_match_node_id = no_match_node_id
        self.error_node = error_node

        if actions is None:
            self.conditional_actions = []
        else:
            self.conditional_actions = actions

    def node_type(self):
        return 'branch-conditions'

    def next_nodes(self):
        nodes = []

        if self.error_node is not None:
            nodes.append((self.error_node, 'Evaluation Error'))

        if self.no_match_node_id is not None:
            nodes.append((self.no_match_node_id, 'No Matches'))

        for conditional_action in self.conditional_actions:
            nodes.append((conditional_action['action'], 'Condition: ' + conditional_action['condition']))

        return nodes

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        try:
            for conditional_action in self.conditional_actions:
                if extras is None:
                    extras = {}

                local_env = extras.copy()
                local_env['logger'] = logger

                result = eval(conditional_action['condition'], {}, extras)

                if result: # nosec # pylint: disable=eval-used
                    transition = DialogTransition(new_state_id=conditional_action['action'])

                    transition.metadata['reason'] = 'matched-condition'
                    transition.metadata['condition'] = conditional_action['condition']
                    transition.metadata['exit_actions'] = []

                    return transition
        except: # pylint: disable=bare-except
            traceback.print_exc()
            
            transition = DialogTransition(new_state_id=self.error_node)

            transition.metadata['reason'] = 'conditional-error'
            transition.metadata['error'] = traceback.format_exc()

            return transition

        if self.no_match_node_id is not None:
            transition = DialogTransition(new_state_id=self.no_match_node_id)
            transition.metadata['reason'] = 'no-matching-conditions'

            return transition

        return None

    def actions(self):
        return[]
