# pylint: disable=line-too-long, super-with-arguments, no-member, cyclic-import

import json
import uuid

from .base_node import BaseNode, MissingNextDialogNodeError
from .dialog_machine import DialogTransition, DialogMachine

class EmbedDialogNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'embed-dialog':
            if ('next_id' in dialog_def) is False:
                raise MissingNextDialogNodeError('next_id missing in: ' + json.dumps(dialog_def, indent=2), dialog_def, 'next_id')

            return EmbedDialogNode(dialog_def['id'], dialog_def['next_id'], dialog_def.get('script_id', None))

        return None

    def __init__(self, node_id, next_node_id, script_id):
        super(EmbedDialogNode, self).__init__(node_id, next_node_id)

        self.script_id = script_id

    def node_type(self):
        return 'embed-dialog'

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments, unused-argument
        if extras is None:
            extras = {}

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'embed-dialog-continue'
        transition.metadata['error'] = 'Unable to replace self with dialog script with ID "%s".' % self.script_id

        return transition

    def actions(self):
        return []

    def replacement_definitions(self, original_definition): # pylint: disable=unused-argument
        from ..models import DialogScript # pylint: disable=import-outside-toplevel

        script = DialogScript.objects.filter(identifier=self.script_id).first()

        if script is not None:
            machine = DialogMachine(script.definition)

            prefix = '%s_%s__' % (self.script_id, uuid.uuid4())

            machine.prefix_nodes(prefix)

            return machine.dialog_definition()

        return None

    def search_text(self):
        values = ['embed-dialog']

        if self.next_node_id is not None:
            values.append(self.next_node_id)

        if self.script_id is not None:
            values.append(self.script_id)

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
