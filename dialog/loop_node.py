# pylint: disable=line-too-long, super-with-arguments

import json

from .base_node import BaseNode, DialogError, fetch_default_logger
from .dialog_machine import DialogTransition

class LoopNode(BaseNode):
    def __init__(self, node_id, next_node_id, iterations, loop_node_id):
        super(LoopNode, self).__init__(node_id, next_node_id)

        self.iterations = iterations
        self.loop_node_id = loop_node_id

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        loop_count = 0

        if last_transition is not None:
            loop_count = last_transition.dialog.transitions.filter(state_id=self.node_id).count()

        if loop_count < self.iterations:
            transition = DialogTransition(new_state_id=self.loop_node_id)

            transition.metadata['reason'] = 'next-loop'
            transition.metadata['loop_iterations'] = self.iterations
            transition.metadata['loop_iteration'] = loop_count

            return transition

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'finished-loop'
        transition.metadata['loop_iterations'] = self.iterations
        transition.metadata['loop_iteration'] = loop_count

        return transition

    def actions(self):
        return[]

    def node_type(self):
        return 'loop'

    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'loop':
            if ('next_id' in dialog_def) is False:
                raise DialogError('next_id missing in: ' + json.dumps(dialog_def, indent=2))

            if ('loop_id' in dialog_def) is False:
                raise DialogError('loop_id missing in: ' + json.dumps(dialog_def, indent=2))

            if ('iterations' in dialog_def) is False:
                raise DialogError('iterations missing in: ' + json.dumps(dialog_def, indent=2))

            return LoopNode(dialog_def['id'], dialog_def['next_id'], dialog_def['iterations'], dialog_def['loop_id'])

        return None
