# pylint: disable=line-too-long, super-with-arguments

from django.utils import timezone

from .base_node import BaseNode, fetch_default_logger
from .dialog_machine import DialogTransition

class ExternalChoiceNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'external-choice':
            prompt_node = ExternalChoiceNode(dialog_def['id'], dialog_def['actions'])

            if 'timeout' in dialog_def:
                prompt_node.timeout = dialog_def['timeout']

            if 'timeout_node_id' in dialog_def:
                prompt_node.timeout_node_id = dialog_def['timeout_node_id']

            return prompt_node

        return None

    def __init__(self, node_id, actions, timeout=300, timeout_node_id=None): # pylint: disable=too-many-arguments
        super(ExternalChoiceNode, self).__init__(node_id, node_id)

        if actions is None:
            self.choice_actions = []
        else:
            self.choice_actions = actions

        self.timeout = timeout
        self.timeout_node_id = timeout_node_id

    def node_type(self):
        return 'external-choice'

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        if ('is_external' in extras) and extras['is_external']:
            if response is not None: # pylint: disable=no-else-return
                matched_action = None

                for action in self.choice_actions:
                    if action['identifier'] == response:
                        matched_action = action

                if matched_action is not None:
                    transition = DialogTransition(new_state_id=matched_action['action'])

                    transition.metadata['reason'] = 'valid-choice'
                    transition.metadata['response'] = response
                    transition.metadata['actions'] = self.choice_actions
                    transition.metadata['exit_actions'] = [{
                        'type': 'store-value',
                        'key': self.node_id,
                        'value': response
                    }]

                    return transition

        if response is None and last_transition is not None and self.timeout_node_id is not None:
            now = timezone.now()

            if (now - last_transition.when).total_seconds() > self.timeout:
                transition = DialogTransition(new_state_id=self.timeout_node_id)

                transition.metadata['reason'] = 'timeout'
                transition.metadata['timeout_duration'] = self.timeout

                return transition

        if last_transition is not None:
            if last_transition.state_id != self.node_id:
                transition = DialogTransition(new_state_id=self.node_id)

                transition.metadata['reason'] = 'choice-init'

                return transition

        return None

    def actions(self):
        available_choices = {
            'type': 'external-choice',
            'choices': []
        }

        for action in self.choice_actions:
            available_choices['choices'].append({
                'identifier': action['identifier'],
                'label': action['label']
            })

        return [available_choices]
