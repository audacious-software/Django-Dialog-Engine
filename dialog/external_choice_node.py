# pylint: disable=line-too-long, super-with-arguments

from django.utils import timezone

from .base_node import BaseNode, fetch_default_logger
from .dialog_machine import DialogTransition

class ExternalChoiceNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'external-choice':
            choice_node = ExternalChoiceNode(dialog_def['id'], dialog_def['actions'])

            timeout = dialog_def.get('timeout', None)
            timeout_node_id = dialog_def.get('timeout_node_id', None)

            if timeout is not None and timeout_node_id is not None:
                choice_node.timeout = timeout
                choice_node.timeout_node_id = timeout_node_id

            return choice_node

        return None

    def __init__(self, node_id, actions, timeout=300, timeout_node_id=None): # pylint: disable=too-many-arguments
        super(ExternalChoiceNode, self).__init__(node_id, node_id)

        if actions is None:
            self.choice_actions = []
        else:
            self.choice_actions = actions

        self.timeout = timeout
        self.timeout_node_id = timeout_node_id

    def prefix_nodes(self, prefix):
        super().prefix_nodes(prefix) # pylint: disable=missing-super-argument

        if self.timeout_node_id is not None:
            self.timeout_node_id = prefix + self.timeout_node_id

        for action in self.choice_actions:
            action['action'] = prefix + action['action']

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        if 'next_id' in node_def:
            del node_def['next_id']

        if self.timeout is not None:
            node_def['timeout'] = self.timeout

        if self.timeout_node_id is not None:
            node_def['timeout_node_id'] = self.timeout_node_id

        node_def['actions'] = self.choice_actions

        return node_def

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

    def search_text(self):
        values = ['external-choice']

        for action in self.choice_actions:
            values.append(action['identifier'])
            values.append(action['label'])

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
