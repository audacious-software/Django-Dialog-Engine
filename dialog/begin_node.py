# pylint: disable=line-too-long, super-with-arguments

from .base_node import BaseNode, fetch_default_logger, DialogTransition

class BeginNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'begin':
            return BeginNode(dialog_def['id'], dialog_def['next_id'])

        return None

    def node_type(self):
        return 'begin'

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'begin-dialog'

        return transition

    def actions(self):
        return []
