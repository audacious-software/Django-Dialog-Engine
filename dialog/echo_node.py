# pylint: disable=line-too-long, super-with-arguments

import json

from .base_node import BaseNode, MissingNextDialogNodeError, fetch_default_logger
from .dialog_machine import DialogTransition

class EchoNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'echo':
            if ('next_id' in dialog_def) is False:
                raise MissingNextDialogNodeError('next_id missing in: ' + json.dumps(dialog_def, indent=2), dialog_def, 'next_id')

            return EchoNode(dialog_def['id'], dialog_def['next_id'], dialog_def['message'])

        return None

    def __init__(self, node_id, next_node_id, message):
        super(EchoNode, self).__init__(node_id, next_node_id)

        self.message = message

    def node_type(self):
        return 'echo'

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments, unused-argument
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'echo-continue'

        return transition

    def actions(self):
        return[{
            'type': 'echo',
            'message': self.message
        }]
