# pylint: disable=line-too-long, useless-object-inheritance, super-with-arguments

from builtins import str # pylint: disable=redefined-builtin
from builtins import object # pylint: disable=redefined-builtin

import importlib
import json
import logging
import re
import sys

import numpy

from django.conf import settings
from django.utils import timezone
from django.utils.encoding import smart_str

from past.builtins import basestring # pylint: disable=redefined-builtin

def fetch_default_logger():
    logger = logging.getLogger('django-dialog-engine')
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger

class DialogError(Exception):
    pass

class DialogMachine(object):
    def __init__(self, definition, metadata=None, django_object=None):
        self.all_nodes = {}
        self.current_node = None
        self.start_node = None

        self.django_object = django_object

        if metadata is None:
            metadata = {}

        self.metadata = metadata

        for node_def in definition:
            node = None

            for app in settings.INSTALLED_APPS:
                try:
                    importlib.import_module(app + '.dialog_api')
                except ImportError:
                    pass
                except AttributeError:
                    pass

            for cls in BaseNode.__subclasses__():
                if node is None:
                    node = cls.parse(node_def)

            if node is None:
                raise DialogError('Unable to parse node definition: ' + json.dumps(node_def, indent=2))

            self.all_nodes[node.node_id] = node

            if self.current_node is None and isinstance(node, Begin):
                self.current_node = node

    def advance_to(self, node_id):
        try:
            self.current_node = self.all_nodes[node_id]
        except KeyError:
            pass # Cannot continue - stay in same place.

    def evaluate(self, response=None, last_transition=None, extras=None, logger=None):
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        if self.current_node is None:
            return None

        transition = self.current_node.evaluate(self, response, last_transition, extras, logger)

        if transition is not None:
            if transition.new_state_id in self.all_nodes:
                if ('exit_actions' in transition.metadata) is False:
                    transition.metadata['actions'] = []
                else:
                    transition.metadata['actions'] = transition.metadata['exit_actions']

                transition.metadata['actions'] += self.actions_for_state(transition.new_state_id)

                if transition.metadata['actions']:
                    pass
                else:
                    transition.metadata['actions'] = None

        return transition

    def prior_transitions(self, new_state_id, prior_state_id, reason=None):
        if self.django_object is not None:
            return self.django_object.prior_transitions(new_state_id, prior_state_id, reason)

        return []

    def actions_for_state(self, state_id):
        actions = self.all_nodes[state_id].actions()

        if actions is None:
            actions = []

        return actions


class DialogTransition(object): # pylint: disable=too-few-public-methods
    def __init__(self, new_state_id, metadata=None):
        self.new_state_id = new_state_id

        self.refresh = False

        if metadata is None:
            metadata = {}

        self.metadata = metadata

class BaseNode(object):
    def __init__(self, node_id, next_node_id=None):
        self.node_id = node_id
        self.next_node_id = next_node_id

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=unused-argument, too-many-arguments
        raise DialogError('Unimplemented method: evaluate. Class: ' + self.__class__.__name__)

    def actions(self):
        raise DialogError('Unimplemented method: actions. Class: ' + self.__class__.__name__)

    @staticmethod
    def parse(dialog_def): # pylint: disable=unused-argument
        return None

class Prompt(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'prompt':
            prompt_node = Prompt(dialog_def['id'], dialog_def['next_id'], dialog_def['prompt'])

            if 'timeout' in dialog_def:
                prompt_node.timeout = dialog_def['timeout']

            if 'timeout_node_id' in dialog_def:
                prompt_node.timeout_node_id = dialog_def['timeout_node_id']

            if 'invalid_response_node_id' in dialog_def:
                prompt_node.invalid_response_node_id = dialog_def['invalid_response_node_id']

            if 'valid_patterns' in dialog_def:
                prompt_node.valid_patterns = dialog_def['valid_patterns']

            return prompt_node

        return None

    def __init__(self, node_id, next_node_id, prompt, timeout=300, timeout_node_id=None, invalid_response_node_id=None, valid_patterns=None): # pylint: disable=too-many-arguments
        super(Prompt, self).__init__(node_id, next_node_id)

        self.prompt = prompt
        self.timeout = timeout

        self.timeout_node_id = timeout_node_id
        self.invalid_response_node_id = invalid_response_node_id

        if valid_patterns is None:
            self.valid_patterns = []
        else:
            self.valid_patterns = valid_patterns

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()


        if response is None and last_transition is not None and self.timeout_node_id is not None:
            now = timezone.now()

            if (now - last_transition.when).total_seconds() > self.timeout:
                transition = DialogTransition(new_state_id=self.timeout_node_id)

                transition.metadata['reason'] = 'timeout'
                transition.metadata['timeout_duration'] = self.timeout

                return transition

        if response is not None:
            valid_response = False

            if self.valid_patterns:
                pass
            else:
                valid_response = True

            for pattern in self.valid_patterns:
                if re.match(pattern, response) is not None:
                    valid_response = True

            if valid_response is False:
                if self.invalid_response_node_id is not None:
                    transition = DialogTransition(new_state_id=self.invalid_response_node_id)

                    transition.metadata['reason'] = 'invalid-response'
                    transition.metadata['response'] = response
                    transition.metadata['valid_patterns'] = self.valid_patterns

                    return transition

                return None # What to do here?

            transition = DialogTransition(new_state_id=self.next_node_id)

            transition.metadata['reason'] = 'valid-response'
            transition.metadata['response'] = response
            transition.metadata['valid_patterns'] = self.valid_patterns
            transition.metadata['exit_actions'] = [{
                'type': 'store-value',
                'key': self.node_id,
                'value': response
            }]

            return transition

        transition = DialogTransition(new_state_id=self.node_id)

        transition.metadata['reason'] = 'prompt-init'

        return transition

    def actions(self):
        return[{
            'type': 'echo',
            'message': self.prompt
        }, {
            'type': 'wait-for-input',
            'timeout': self.timeout
        }]

class Echo(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'echo':
            if ('next_id' in dialog_def) is False:
                raise DialogError('next_id missing in: ' + json.dumps(dialog_def, indent=2))

            return Echo(dialog_def['id'], dialog_def['next_id'], dialog_def['message'])

        return None

    def __init__(self, node_id, next_node_id, message):
        super(Echo, self).__init__(node_id, next_node_id)

        self.message = message

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'echo-continue'

        return transition

    def actions(self):
        return[{
            'type': 'echo',
            'message': self.message
        }]

class End(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'end':
            return End(dialog_def['id'], None)

        return None

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

class Begin(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'begin':
            return Begin(dialog_def['id'], dialog_def['next_id'])

        return None

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'begin-dialog'

        return transition

    def actions(self):
        return []

class Pause(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'pause':
            return Pause(dialog_def['id'], dialog_def['next_id'], dialog_def['duration'])

        return None

    def __init__(self, node_id, next_node_id, duration):
        super(Pause, self).__init__(node_id, next_node_id)

        self.duration = duration

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

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

class If(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'if':
            return If(dialog_def['id'], dialog_def['next_id'], dialog_def['all_true'], dialog_def['false_id'])

        return None

    def __init__(self, node_id, next_node_id, all_true, false_id):
        super(If, self).__init__(node_id, next_node_id)

        self.all_true = all_true
        self.false_id = false_id

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-branches, too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        is_all_true = True

        for condition in self.all_true:
            key = condition['key']

            value = None

            if 'values' in dialog.metadata:
                if key in dialog.metadata['values']:
                    value = dialog.metadata['values'][key]

            if value is None:
                raise Exception('No value for "' + key + '" in dialog metadata. The ordering of the dialog may be incorrect!')

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

class LoopAction(BaseNode):
    def __init__(self, node_id, next_node_id, iterations, loop_node_id):
        super(LoopAction, self).__init__(node_id, next_node_id)

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

    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'loop':
            if ('next_id' in dialog_def) is False:
                raise DialogError('next_id missing in: ' + json.dumps(dialog_def, indent=2))

            if ('loop_id' in dialog_def) is False:
                raise DialogError('loop_id missing in: ' + json.dumps(dialog_def, indent=2))

            if ('iterations' in dialog_def) is False:
                raise DialogError('iterations missing in: ' + json.dumps(dialog_def, indent=2))

            return LoopAction(dialog_def['id'], dialog_def['next_id'], dialog_def['iterations'], dialog_def['loop_id'])

        return None


class WhileAction(BaseNode):
    def __init__(self, action_id, action_type, test, actions):
        super(WhileAction, self).__init__(action_id, action_type)

        self.test = test
        self.actions = actions

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

        return None

    def actions(self): # nosec
        print('SCRIPT: ' + self.actions_script)

        code = compile(self.actions_script, '<string>', 'exec')

        custom_actions = []

        eval(code, {}, {'definition': self.definition, 'actions': custom_actions}) # pylint: disable=eval-used

        print('ACTIONS: ' + str(custom_actions))

        for action in custom_actions:
            if isinstance(action['type'], basestring) is False:
                raise Exception(str(action) + ' is not a valid action. Verify that the "type" key is present and is a string.')

        return custom_actions

class BranchingPrompt(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'branch-prompt':
            prompt_node = BranchingPrompt(dialog_def['id'], dialog_def['actions'], dialog_def['prompt'])

            if 'no_match' in dialog_def:
                prompt_node.invalid_response_node_id = dialog_def['no_match']

            if 'timeout' in dialog_def:
                prompt_node.timeout = dialog_def['timeout']

            if 'timeout_iterations' in dialog_def:
                prompt_node.timeout_iterations = dialog_def['timeout_iterations']

            if 'timeout_node_id' in dialog_def:
                prompt_node.timeout_node_id = dialog_def['timeout_node_id']


            return prompt_node

        return None

    def __init__(self, node_id, actions, prompt, invalid_response_node_id=None, timeout=300, timeout_node_id=None, timeout_iterations=None): # pylint: disable=too-many-arguments
        super(BranchingPrompt, self).__init__(node_id, node_id)

        self.prompt = prompt

        self.invalid_response_node_id = invalid_response_node_id

        if actions is None:
            self.pattern_actions = []
        else:
            self.pattern_actions = actions

        self.timeout = timeout
        self.timeout_node_id = timeout_node_id
        self.timeout_iterations = timeout_iterations

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments, too-many-return-statements, too-many-branches
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        if response is not None: # pylint: disable=no-else-return
            matched_action = None

            for action in self.pattern_actions:
                if re.match(action['pattern'], response, re.IGNORECASE) is not None:
                    matched_action = action

            if matched_action is None:
                if self.invalid_response_node_id is not None:
                    transition = DialogTransition(new_state_id=self.invalid_response_node_id)

                    transition.metadata['reason'] = 'invalid-response'
                    transition.metadata['response'] = response
                    transition.metadata['actions'] = self.pattern_actions

                    transition.refresh = True

                    return transition

                return None # What to do here?

            transition = DialogTransition(new_state_id=matched_action['action'])

            transition.metadata['reason'] = 'valid-response'
            transition.metadata['response'] = response
            transition.metadata['actions'] = self.pattern_actions
            transition.metadata['exit_actions'] = [{
                'type': 'store-value',
                'key': self.node_id,
                'value': response
            }]

            return transition
        elif last_transition is not None and self.timeout_node_id is not None:
            now = timezone.now()

            if (now - last_transition.when).total_seconds() > self.timeout:
                can_timeout = True

                if self.timeout_iterations is not None:
                    prior_timeouts = dialog.prior_transitions(new_state_id=self.timeout_node_id, prior_state_id=self.node_id, reason='timeout')

                    if len(prior_timeouts) >= self.timeout_iterations:
                        can_timeout = False

                if can_timeout:
                    transition = DialogTransition(new_state_id=self.timeout_node_id)
                    transition.refresh = True

                    transition.metadata['reason'] = 'timeout'
                    transition.metadata['timeout_duration'] = self.timeout

                    return transition

                return None

        if last_transition is not None:
            if last_transition.state_id != self.node_id:
                transition = DialogTransition(new_state_id=self.node_id)

                transition.metadata['reason'] = 'prompt-init'

                return transition

        return None

    def actions(self):
        return[{
            'type': 'echo',
            'message': self.prompt
        }]

class ExternalChoice(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'external-choice':
            prompt_node = ExternalChoice(dialog_def['id'], dialog_def['actions'])

            if 'timeout' in dialog_def:
                prompt_node.timeout = dialog_def['timeout']

            if 'timeout_node_id' in dialog_def:
                prompt_node.timeout_node_id = dialog_def['timeout_node_id']

            return prompt_node

        return None

    def __init__(self, node_id, actions, timeout=300, timeout_node_id=None): # pylint: disable=too-many-arguments
        super(ExternalChoice, self).__init__(node_id, node_id)

        if actions is None:
            self.choice_actions = []
        else:
            self.choice_actions = actions

        self.timeout = timeout
        self.timeout_node_id = timeout_node_id

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        if ('is_external' in extras) and extras['is_external']:
            if response is not None: # pylint: disable=no-else-return
                matched_action = None

                for action in self.choice_actions:
                    if action['identifier'] == response:
                        matched_action = action

                if matched_action is not None:
                    transition = DialogTransition(new_state_id=matched_action['action'])

                    transition.metadata['reason'] = 'valid-choice'
                    transition.metadata['response'] = response
                    transition.metadata['actions'] = self.choice_actions
                    transition.metadata['exit_actions'] = [{
                        'type': 'store-value',
                        'key': self.node_id,
                        'value': response
                    }]

                    return transition

        if response is None and last_transition is not None and self.timeout_node_id is not None:
            now = timezone.now()

            if (now - last_transition.when).total_seconds() > self.timeout:
                transition = DialogTransition(new_state_id=self.timeout_node_id)

                transition.metadata['reason'] = 'timeout'
                transition.metadata['timeout_duration'] = self.timeout

                return transition

        if last_transition is not None:
            if last_transition.state_id != self.node_id:
                transition = DialogTransition(new_state_id=self.node_id)

                transition.metadata['reason'] = 'choice-init'

                return transition

        return None

    def actions(self):
        available_choices = {
            'type': 'external-choice',
            'choices': []
        }

        for action in self.choice_actions:
            available_choices['choices'].append({
                'identifier': action['identifier'],
                'label': action['label']
            })

        return [available_choices]

class RandomBranch(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'random-branch':
            branch_node = RandomBranch(dialog_def['id'], dialog_def['actions'])

            return branch_node

        return None

    def __init__(self, node_id, actions):
        super(RandomBranch, self).__init__(node_id, node_id)

        if actions is None:
            self.random_actions = []
        else:
            self.random_actions = actions

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        choices = []
        weights = []

        for action in self.random_actions:
            choices.append(action['action'])
            weights.append(action['weight'])

        chosen = numpy.random.choice(choices, p=weights)

        transition = DialogTransition(new_state_id=chosen)

        transition.metadata['reason'] = 'random-branch'

        return transition

    def actions(self):
        return []
