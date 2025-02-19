# pylint: disable=line-too-long, super-with-arguments

from django.utils import timezone

from .base_node import BaseNode, DialogTransition

class TimeElapsedInterruptNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'time-elapsed-interrupt':
            interrupt_node = TimeElapsedInterruptNode(dialog_def['id'], dialog_def['hours_elapsed'], dialog_def['minutes_elapsed'], dialog_def['next_id'])

            return interrupt_node

        return None

    def __init__(self, node_id, hours_elapsed, minutes_elapsed, next_node_id):
        super(TimeElapsedInterruptNode, self).__init__(node_id, next_node_id)

        self.hours_elapsed = hours_elapsed
        self.minutes_elapsed = minutes_elapsed

        if self.hours_elapsed is None:
            self.hours_elapsed = 0

        if self.minutes_elapsed is None:
            self.minutes_elapsed = 0

    def node_type(self):
        return 'time-elapsed-interrupt'

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        node_def['hours_elapsed'] = self.hours_elapsed
        node_def['minutes_elapsed'] = self.minutes_elapsed

        return node_def

    def should_fire(self, last_transition=None, ignore_transitions=False):
        if last_transition is not None and self.hours_elapsed is not None and self.minutes_elapsed is not None:
            elapsed_seconds = (self.hours_elapsed * 60 * 60) + (self.minutes_elapsed * 60)

            dialog = last_transition.dialog

            now = timezone.now()

            if (now - dialog.started).total_seconds() >= elapsed_seconds:
                if ignore_transitions:
                    return True

                existing_transitions = dialog.transitions.filter(state_id=self.node_id)

                if existing_transitions.count() > 0:
                    return False # Already fired / entered state

                return True

        return False

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = ()

        if self.should_fire(last_transition, ignore_transitions=True):
            transition = DialogTransition(new_state_id=self.next_node_id)

            transition.metadata['reason'] = 'interrupt-time-elapsed'
            transition.metadata['time_duration'] = (self.hours_elapsed * 60 * 60) + (self.minutes_elapsed * 60)

            return transition

        return None

    def actions(self):
        return []

    def search_text(self):
        values = ['time-elapsed-interrupt']

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
