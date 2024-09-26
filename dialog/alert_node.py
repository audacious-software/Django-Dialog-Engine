# pylint: disable=line-too-long, super-with-arguments, no-member, fixme

import json

from .base_node import BaseNode, MissingNextDialogNodeError, fetch_default_logger
from .dialog_machine import DialogTransition

class AlertNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'alert':
            if ('next_id' in dialog_def) is False:
                raise MissingNextDialogNodeError('next_id missing in: ' + json.dumps(dialog_def, indent=2), dialog_def, 'next_id')

            return AlertNode(dialog_def['id'], dialog_def['next_id'], dialog_def['message'])

        return None

    def __init__(self, node_id, next_node_id, message):
        super(AlertNode, self).__init__(node_id, next_node_id)

        self.message = message

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'alert-continue'

        return transition

    def node_type(self):
        return 'alert'

    def actions(self):
        return[{
            'type': 'raise-alert',
            'message': self.message
        }]

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        node_def['message'] = self.message

        return node_def

    def search_text(self):
        values = ['raise-alert']

        if self.message is not None:
            values.append(self.message)

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
