# pylint: disable=line-too-long, super-with-arguments

import json

from .base_node import BaseNode, MissingNextDialogNodeError, fetch_default_logger
from .dialog_machine import DialogTransition

class UpdateVariableNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'update-variable':
            if ('next_id' in dialog_def) is False:
                raise MissingNextDialogNodeError('next_id missing in: ' + json.dumps(dialog_def, indent=2), dialog_def, 'next_id')

            return UpdateVariableNode(dialog_def['id'], dialog_def['next_id'], dialog_def['key'], dialog_def['value'], dialog_def['operation'], dialog_def.get('replacement', None))

        return None

    def __init__(self, node_id, next_node_id, key, value, operation, replacement=None): # pylint: disable=too-many-arguments
        super(UpdateVariableNode, self).__init__(node_id, next_node_id)

        self.key = key
        self.value = value
        self.operation = operation
        self.replacement = replacement

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'set-variable-continue'
        transition.metadata['exit_actions'] = [{
            'type': 'update-value',
            'key': self.key,
            'value': self.value,
            'replacement': self.replacement,
            'operation': self.operation,
        }]

        return transition

    def node_type(self):
        return 'update-variable'

    def actions(self):
        return []

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        node_def['key'] = self.key
        node_def['value'] = self.value
        node_def['operation'] = self.operation
        node_def['replacement'] = self.replacement

        return node_def

    def search_text(self):
        values = ['update-variable']

        if self.key is not None:
            values.append(self.key)

        if self.value is not None:
            values.append(self.value)

        if self.replacement is not None:
            values.append(self.replacement)

        if self.operation is not None:
            values.append(self.operation)

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
