# pylint: disable=line-too-long, super-with-arguments

import re

from django.utils import timezone

from .base_node import BaseNode, fetch_default_logger
from .dialog_machine import DialogTransition

class PromptNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'prompt':
            prompt_node = PromptNode(dialog_def['id'], dialog_def['next_id'], dialog_def['prompt'])

            if 'timeout' in dialog_def:
                prompt_node.timeout = dialog_def['timeout']

            if 'timeout_node_id' in dialog_def:
                prompt_node.timeout_node_id = dialog_def['timeout_node_id']

            if 'invalid_response_node_id' in dialog_def:
                prompt_node.invalid_response_node_id = dialog_def['invalid_response_node_id']

            if 'valid_patterns' in dialog_def:
                prompt_node.valid_patterns = dialog_def['valid_patterns']

            return prompt_node

        return None

    def __init__(self, node_id, next_node_id, prompt, timeout=300, timeout_node_id=None, invalid_response_node_id=None, valid_patterns=None): # pylint: disable=too-many-arguments
        super(PromptNode, self).__init__(node_id, next_node_id)

        self.prompt = prompt
        self.timeout = timeout

        self.timeout_node_id = timeout_node_id
        self.invalid_response_node_id = invalid_response_node_id

        if valid_patterns is None:
            self.valid_patterns = []
        else:
            self.valid_patterns = valid_patterns

    def node_type(self):
        return 'prompt'

    def prefix_nodes(self, prefix):
        super().prefix_nodes(prefix)

        if self.timeout_node_id is not None:
            self.timeout_node_id = prefix + self.timeout_node_id

        if self.invalid_response_node_id is not None:
            self.invalid_response_node_id = prefix + self.invalid_response_node_id

    def node_definition(self):
        node_def = super().node_definition()

        if self.timeout is not None:
            node_def['timeout'] = self.timeout

        if self.timeout_node_id is not None:
            node_def['timeout_node_id'] = self.timeout_node_id

        if self.invalid_response_node_id is not None:
            node_def['invalid_response_node_id'] = self.timeout_node_id

        node_def['valid_patterns'] = self.valid_patterns

        return node_def

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()


        if response is None and last_transition is not None and self.timeout_node_id is not None:
            now = timezone.now()

            if (now - last_transition.when).total_seconds() > self.timeout:
                transition = DialogTransition(new_state_id=self.timeout_node_id)

                transition.metadata['reason'] = 'timeout'
                transition.metadata['timeout_duration'] = self.timeout

                return transition

        if response is not None:
            valid_response = False

            if self.valid_patterns:
                pass
            else:
                valid_response = True

            for pattern in self.valid_patterns:
                if re.match(pattern, response) is not None:
                    valid_response = True

            if valid_response is False:
                if self.invalid_response_node_id is not None:
                    transition = DialogTransition(new_state_id=self.invalid_response_node_id)

                    transition.metadata['reason'] = 'invalid-response'
                    transition.metadata['response'] = response
                    transition.metadata['valid_patterns'] = self.valid_patterns

                    return transition

                return None # What to do here?

            transition = DialogTransition(new_state_id=self.next_node_id)

            transition.metadata['reason'] = 'valid-response'
            transition.metadata['response'] = response
            transition.metadata['valid_patterns'] = self.valid_patterns
            transition.metadata['exit_actions'] = [{
                'type': 'store-value',
                'key': self.node_id,
                'value': response
            }]

            return transition

        transition = DialogTransition(new_state_id=self.node_id)

        transition.metadata['reason'] = 'prompt-init'

        return transition

    def actions(self):
        return[{
            'type': 'echo',
            'message': self.prompt
        }, {
            'type': 'wait-for-input',
            'timeout': self.timeout
        }]
