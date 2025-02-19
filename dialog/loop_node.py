# pylint: disable=line-too-long, super-with-arguments

import json

from .base_node import BaseNode, DialogError
from .dialog_machine import DialogTransition

class LoopNode(BaseNode):
    def __init__(self, node_id, next_node_id, iterations, loop_node_id):
        super(LoopNode, self).__init__(node_id, next_node_id)

        self.iterations = iterations
        self.loop_node_id = loop_node_id

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

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

    def prefix_nodes(self, prefix):
        super().prefix_nodes(prefix) # pylint: disable=missing-super-argument

        if self.loop_node_id is not None:
            self.loop_node_id = prefix + self.loop_node_id

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        if 'next_id' in node_def:
            del node_def['next_id']

        if self.loop_node_id is not None:
            node_def['loop_id'] = self.loop_node_id

        node_def['iterations'] = self.iterations

        return node_def

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

    def search_text(self):
        values = ['loop']

        if self.loop_node_id is not None:
            values.append(self.loop_node_id)

        if self.next_node_id is not None:
            values.append(self.next_node_id)

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
