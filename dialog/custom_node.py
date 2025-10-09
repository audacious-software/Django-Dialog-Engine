# pylint: disable=line-too-long, super-with-arguments, eval-used

import importlib
import logging
import traceback

from six import string_types

from django.conf import settings
from django.utils.encoding import smart_str

from .base_node import BaseNode, DialogError
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

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        if 'next_id' in node_def:
            del node_def['next_id']

        node_def['definition'] = self.definition
        node_def['evaluate'] = self.evaluate_script
        node_def['actions'] = self.actions_script

        return node_def

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments, too-many-branches, too-many-positional-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = logging.getLogger(__name__)

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

        for app in settings.INSTALLED_APPS:
            try:
                app_dialog_api = importlib.import_module(app + '.dialog_api')

                app_dialog_api.update_custom_node_environment(local_env)
            except ImportError:
                pass
            except AttributeError:
                pass

        try:
            code = compile(smart_str(self.evaluate_script), '<string>', 'exec')

            eval(code, {}, local_env) # nosec # pylint: disable=eval-used

            if result['details'] is not None and result['next_id'] is not None:
                transition = DialogTransition(new_state_id=result['next_id'])

                transition.metadata = result['details']

                if result['actions'] is not None:
                    for action in result['actions']:
                        if isinstance(action['type'], string_types) is False:
                            raise DialogError('%s is not a valid action. Verify that the "type" key is present and is a string.' % action)

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

    def actions(self):
        logger = logging.getLogger(__name__)

        try:
            code = compile(self.actions_script, '<string>', 'exec')

            custom_actions = []

            eval(code, {}, {'definition': self.definition, 'actions': custom_actions}) #nosec B307

            for action in custom_actions:
                if isinstance(action['type'], string_types) is False:
                    raise DialogError('%s is not a valid action. Verify that the "type" key is present and is a string.' % action)

            return custom_actions
        except: # pylint: disable=bare-except
            logger.error('Error in custom node (%s):', self.node_id)
            logger.error('Script:\n%s', self.actions_script)
            logger.error(traceback.format_exc())

        return []

    def search_text(self):
        values = ['custom']

        if self.actions_script is not None:
            values.append(self.actions_script)

        if self.evaluate_script is not None:
            values.append(self.evaluate_script)

        return '%s\n%s' % (super().search_text(), '\n'.join(values)) # pylint: disable=missing-super-argument
