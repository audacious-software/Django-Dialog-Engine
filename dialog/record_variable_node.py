# pylint: disable=line-too-long, super-with-arguments

import json

from .base_node import BaseNode, MissingNextDialogNodeError, fetch_default_logger
from .dialog_machine import DialogTransition

class RecordVariableNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'record-variable':
            if ('next_id' in dialog_def) is False:
                raise MissingNextDialogNodeError('next_id missing in: ' + json.dumps(dialog_def, indent=2), dialog_def, 'next_id')

            return RecordVariableNode(dialog_def['id'], dialog_def['next_id'], dialog_def['key'], dialog_def['value'])

        return None

    def __init__(self, node_id, next_node_id, key, value):
        super(RecordVariableNode, self).__init__(node_id, next_node_id)

        self.key = key
        self.value = value

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'set-variable-continue'
        transition.metadata['exit_actions'] = [{
            'type': 'store-value',
            'key': self.key,
            'value': self.value
        }]

        return transition

    def node_type(self):
        return 'record-variable'

    def actions(self):
        return []

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        node_def['key'] = self.key
        node_def['value'] = self.value

        return node_def

    def search_text(self):
        values = ['record-variable', self.key, self.value]

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
