# pylint: disable=line-too-long, super-with-arguments

import re

from django.utils import timezone

from .base_node import BaseNode, fetch_default_logger
from .dialog_machine import DialogTransition

class BranchingPromptNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'branch-prompt':
            prompt_node = BranchingPromptNode(dialog_def['id'], dialog_def['actions'], dialog_def['prompt'])

            if 'no_match' in dialog_def:
                prompt_node.invalid_response_node_id = dialog_def['no_match']

            if 'timeout' in dialog_def:
                prompt_node.timeout = dialog_def['timeout']

            if 'timeout_iterations' in dialog_def:
                prompt_node.timeout_iterations = dialog_def['timeout_iterations']

            if 'timeout_node_id' in dialog_def:
                prompt_node.timeout_node_id = dialog_def['timeout_node_id']

            return prompt_node

        return None

    def __init__(self, node_id, actions, prompt, invalid_response_node_id=None, timeout=300, timeout_node_id=None, timeout_iterations=None): # pylint: disable=too-many-arguments
        super(BranchingPromptNode, self).__init__(node_id, node_id)

        self.prompt = prompt

        self.invalid_response_node_id = invalid_response_node_id

        if actions is None:
            self.pattern_actions = []
        else:
            self.pattern_actions = actions

        self.timeout = timeout
        self.timeout_node_id = timeout_node_id
        self.timeout_iterations = timeout_iterations

    def node_type(self):
        return 'branch-prompt'

    def next_nodes(self):
        nodes = []

        if self.invalid_response_node_id is not None:
            nodes.append((self.invalid_response_node_id, 'Invalid Response'))

        if self.timeout_node_id is not None:
            nodes.append((self.timeout_node_id, 'Response Timed Out'))

        for pattern_action in self.pattern_actions:
            nodes.append((pattern_action['action'], 'Response Matched Pattern: ' + pattern_action['pattern']))

        return nodes

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments, too-many-return-statements, too-many-branches
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        if response is not None: # pylint: disable=no-else-return
            matched_action = None

            for action in self.pattern_actions:
                if matched_action is None and re.search(action['pattern'], response, re.IGNORECASE) is not None:
                    matched_action = action

            if matched_action is None:
                if self.invalid_response_node_id is not None:
                    transition = DialogTransition(new_state_id=self.invalid_response_node_id)

                    transition.metadata['reason'] = 'invalid-response'
                    transition.metadata['response'] = response
                    transition.metadata['actions'] = self.pattern_actions

                    transition.refresh = True

                    transition.metadata['exit_actions'] = [{
                        'type': 'store-value',
                        'key': self.node_id,
                        'value': response
                    }]

                    return transition

                return None # What to do here?

            transition = DialogTransition(new_state_id=matched_action['action'])

            transition.metadata['reason'] = 'valid-response'
            transition.metadata['response'] = response
            transition.metadata['actions'] = self.pattern_actions
            transition.metadata['exit_actions'] = [{
                'type': 'store-value',
                'key': self.node_id,
                'value': response
            }]

            return transition
        elif last_transition is not None and self.timeout_node_id is not None:
            now = timezone.now()

            if (now - last_transition.when).total_seconds() > self.timeout:
                can_timeout = True

                if self.timeout_iterations is not None:
                    prior_timeouts = dialog.prior_transitions(new_state_id=self.timeout_node_id, prior_state_id=self.node_id, reason='timeout')

                    if len(prior_timeouts) >= self.timeout_iterations:
                        can_timeout = False

                if can_timeout:
                    transition = DialogTransition(new_state_id=self.timeout_node_id)
                    transition.refresh = True

                    transition.metadata['reason'] = 'timeout'
                    transition.metadata['timeout_duration'] = self.timeout

                    return transition

                return None

        if last_transition is not None:
            if last_transition.state_id != self.node_id:
                transition = DialogTransition(new_state_id=self.node_id)

                transition.metadata['reason'] = 'prompt-init'

                return transition

        return None

    def actions(self):
        return[{
            'type': 'echo',
            'message': self.prompt
        }]