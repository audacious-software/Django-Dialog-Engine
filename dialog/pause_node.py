# pylint: disable=line-too-long, super-with-arguments

from django.utils import timezone

from .base_node import BaseNode
from .dialog_machine import DialogTransition

class PauseNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'pause':
            if ('next_id' in dialog_def) is False:
                dialog_def['next_id'] = dialog_def['id']

            return PauseNode(dialog_def['id'], dialog_def['next_id'], dialog_def['duration'])

        return None

    def __init__(self, node_id, next_node_id, duration):
        super(PauseNode, self).__init__(node_id, next_node_id)

        self.duration = duration

    def node_type(self):
        return 'pause'

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments, too-many-positional-arguments
        if extras is None:
            extras = {}

        now = timezone.now()

        if (now - last_transition.when).total_seconds() > self.duration:
            transition = DialogTransition(new_state_id=self.next_node_id)

            transition.metadata['reason'] = 'pause-elapsed'
            transition.metadata['pause_duration'] = self.duration

            return transition

        return None

    def actions(self):
        return [{
            'type': 'pause',
            'duration': self.duration
        }]

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        node_def['duration'] = self.duration

        return node_def

    def search_text(self):
        values = ['pause']

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
