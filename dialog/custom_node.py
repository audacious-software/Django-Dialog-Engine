# pylint: disable=line-too-long, super-with-arguments

import traceback

from past.builtins import basestring # pylint: disable=redefined-builtin

from django.utils.encoding import smart_str

from .base_node import BaseNode, fetch_default_logger
from .dialog_machine import DialogTransition

class CustomNode(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'custom':
            return CustomNode(dialog_def['id'], dialog_def['definition'], dialog_def['evaluate'], dialog_def['actions'])

        return None

    def __init__(self, node_id, definition, evaluate_script, actions_script): # pylint: disable=too-many-arguments
        super(CustomNode, self).__init__(node_id, None)

        self.definition = definition
        self.evaluate_script = evaluate_script
        self.actions_script = actions_script

    def node_type(self):
        return 'custom'

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        last_transition_date = None
        previous_state = None

        if last_transition is not None:
            last_transition_date = last_transition.when
            previous_state = last_transition.state_id

        result = {
            'details': {},
            'actions': [],
            'next_id': None
        }

        if response is not None:
            response = smart_str(response)

        local_env = {
            'definition': self.definition,
            'response': response,
            'last_transition': last_transition_date,
            'previous_state': previous_state,
            'result': result,
            'extras': extras,
            'logger': logger
        }

        try:
            code = compile(smart_str(self.evaluate_script), '<string>', 'exec')

            eval(code, {}, local_env) # nosec # pylint: disable=eval-used

            if result['details'] is not None and result['next_id'] is not None:
                transition = DialogTransition(new_state_id=result['next_id'])

                transition.metadata = result['details']

                if result['actions'] is not None:
                    for action in result['actions']:
                        if isinstance(action['type'], basestring) is False:
                            raise Exception(str(action) + ' is not a valid action. Verify that the "type" key is present and is a string.')

                    transition.metadata['exit_actions'] = result['actions']
                else:
                    transition.metadata['exit_actions'] = []

                return transition
        except: # pylint: disable=bare-except
            traceback.print_exc()

            transition = DialogTransition(new_state_id=None)

            transition.metadata['reason'] = 'dialog-error'
            transition.metadata['error'] = traceback.format_exc()

            return transition


        return None

    def actions(self): # nosec
        try:
            code = compile(self.actions_script, '<string>', 'exec')

            custom_actions = []

            eval(code, {}, {'definition': self.definition, 'actions': custom_actions}) # pylint: disable=eval-used

            for action in custom_actions:
                if isinstance(action['type'], basestring) is False:
                    raise Exception(str(action) + ' is not a valid action. Verify that the "type" key is present and is a string.')

            return custom_actions
        except: # pylint: disable=bare-except
            print('Error in custom node (%s):' % self.node_id)


            traceback.print_exc()

        return []
