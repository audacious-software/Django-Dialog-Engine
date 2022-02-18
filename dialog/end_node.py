# pylint: disable=line-too-long, super-with-arguments

from .base_node import BaseNode, fetch_default_logger, DialogTransition

class EndNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'end':
            return EndNode(dialog_def['id'], None)

        return None

    def node_type(self):
        return 'end'

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        transition = DialogTransition(new_state_id=None)

        transition.metadata['reason'] = 'end-dialog'

        return transition

    def actions(self):
        return []

    def next_nodes(self):
        return []

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        if 'next_id' in node_def:
            del node_def['next_id']

        return node_def
