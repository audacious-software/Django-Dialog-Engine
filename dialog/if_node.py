# pylint: disable=line-too-long, super-with-arguments

from .base_node import BaseNode, DialogError
from .dialog_machine import DialogTransition

class IfNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'if':
            return IfNode(dialog_def['id'], dialog_def['next_id'], dialog_def['all_true'], dialog_def['false_id'])

        return None

    def __init__(self, node_id, next_node_id, all_true, false_id):
        super(IfNode, self).__init__(node_id, next_node_id)

        self.all_true = all_true
        self.false_id = false_id

    def node_type(self):
        return 'if'

    def prefix_nodes(self, prefix):
        super().prefix_nodes(prefix) # pylint: disable=missing-super-argument

        self.false_id = prefix + self.false_id

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        node_def['all_true'] = self.all_true
        node_def['false_id'] = self.false_id

        return node_def

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-branches, too-many-arguments
        if extras is None:
            extras = {}

        is_all_true = True

        for condition in self.all_true:
            key = condition['key']

            value = None

            if 'values' in dialog.metadata:
                if key in dialog.metadata['values']:
                    value = dialog.metadata['values'][key]

            if value is None:
                raise DialogError('No value for "%s" in dialog metadata. The ordering of the dialog may be incorrect!' % key)

            if condition['condition'] == '<':
                if float(value) >= float(condition['value']):
                    is_all_true = False
            elif condition['condition'] == '>':
                if float(value) <= float(condition['value']):
                    is_all_true = False
            elif condition['condition'] == '==':
                if value != condition['value']:
                    is_all_true = False
            elif condition['condition'] == 'contains':
                found = False

                for option in condition['value']:
                    if value.find(option.lower()) >= 0:
                        found = True

                if found is False:
                    is_all_true = False

        if is_all_true:
            transition = DialogTransition(new_state_id=self.next_node_id)

            transition.metadata['reason'] = 'passed-test'

            return transition

        transition = DialogTransition(new_state_id=self.false_id)

        transition.metadata['reason'] = 'failed-test'

        return transition

    def actions(self):
        return []

    def search_text(self):
        values = ['if']

        if self.next_node_id is not None:
            values.append(self.next_node_id)

        if self.false_id is not None:
            values.append(self.false_id)

        for condition in self.all_true:
            values.append(condition['key'])

            values.append(condition['value'])
            values.append(condition['condition'])

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
