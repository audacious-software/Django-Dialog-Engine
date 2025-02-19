# pylint: disable=line-too-long, super-with-arguments

from .base_node import BaseNode
from .dialog_machine import DialogTransition

class InterruptResumeNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'interrupt-resume':
            interrupt_resume_node = InterruptResumeNode(dialog_def['id'], dialog_def['force_top'])

            return interrupt_resume_node

        return None

    def __init__(self, node_id, force_top):
        super(InterruptResumeNode, self).__init__(node_id, node_id)

        if force_top is None:
            self.force_top = False
        else:
            self.force_top = force_top

    def node_type(self):
        return 'interrupt-resume'

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        if 'next_id' in node_def:
            del node_def['next_id']

        node_def['force_top'] = self.force_top

        return node_def

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        next_node_id = dialog.pop_value('django_dialog_engine_interrupt_node_stack')

        if self.force_top:
            next_value = dialog.pop_value('django_dialog_engine_interrupt_node_stack')

            while next_value is not None:
                next_node_id = next_value

                next_value = dialog.pop_value('django_dialog_engine_interrupt_node_stack')

        transition = DialogTransition(new_state_id=next_node_id)

        transition.metadata['reason'] = 'interrupt-resume'
        transition.metadata['force_top'] = self.force_top

        return transition

    def actions(self):
        return []

    def next_nodes(self):
        return []

    def search_text(self):
        values = ['interrupt-resume']

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
