# pylint: disable=line-too-long, useless-object-inheritance, super-with-arguments, too-many-lines

from builtins import str # pylint: disable=redefined-builtin
from builtins import object # pylint: disable=redefined-builtin


import copy
import importlib
import json
import logging
import re
import sys
import uuid
import traceback

from past.builtins import basestring # pylint: disable=redefined-builtin

import lxml # nosec
import numpy
import requests

from jsonpath_ng.ext import parse as jsonpath_ng_parse

from django.conf import settings
from django.utils import timezone
from django.utils.encoding import smart_str

MISSING_NEXT_NODE_KEY = 'django-dialog-engine-missing-next-node-end'

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

class MissingNextDialogNodeError(DialogError):
    def __init__(self, message, container, key):
        super(DialogError, self).__init__(message) # pylint: disable=bad-super-call

        self.container = container
        self.key = key

class DialogMachine(object):
    def __init__(self, definition, metadata=None, django_object=None):
        definition = copy.deepcopy(definition)

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
                    try:
                        node = cls.parse(node_def)
                    except MissingNextDialogNodeError as missing_node:
                        # Automatically add end nodes to dangling node pointers

                        if ('' in self.all_nodes) is False:
                            end_node_def = {
                                'type': 'end',
                                'id': MISSING_NEXT_NODE_KEY
                            }

                            end_node = End.parse(end_node_def)

                            self.all_nodes[end_node.node_id] = end_node

                        missing_node.container[missing_node.key] = MISSING_NEXT_NODE_KEY

                        node = cls.parse(node_def)

                    if node is not None and 'name' in node_def:
                        node.node_name = node_def['name']

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

    def evaluate(self, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-branches
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        if self.current_node is None:
            return None

        if response is not None:
            for key, node in self.all_nodes.items(): # pylint: disable=unused-variable
                if isinstance(node, (Interrupt,)):
                    pattern_matched = node.matches(response)

                    if pattern_matched is not None:
                        transition = DialogTransition(new_state_id=node.node_id)

                        transition.metadata['reason'] = 'interrupt'
                        transition.metadata['pattern'] = 'pattern_matched'
                        transition.metadata['response'] = response
                        transition.metadata['actions'] = []

                        return transition

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

    def pop_value(self, key):
        if self.django_object is not None:
            return self.django_object.pop_value(key)

        return None

    def push_value(self, key, value):
        if self.django_object is not None:
            self.django_object.push_value(key, value)

    def actions_for_state(self, state_id):
        actions = self.all_nodes[state_id].actions()

        if actions is None:
            actions = []

        return actions

    def nodes(self):
        nodes = []

        for node in self.all_nodes.values():
            nodes.append(node)

        return nodes

    def fetch_node(self, node_id):
        return self.all_nodes.get(node_id, None)

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

        self.node_name = node_id

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=unused-argument, too-many-arguments
        raise DialogError('Unimplemented method: evaluate. Class: ' + self.__class__.__name__)

    def actions(self):
        raise DialogError('Unimplemented method: actions. Class: ' + self.__class__.__name__)

    @staticmethod
    def parse(dialog_def): # pylint: disable=unused-argument
        return None

    def next_nodes(self):
        nodes = []

        if self.next_node_id is not None:
            nodes.append((self.next_node_id, 'Next Node'))

        return nodes

    def node_type(self): # pylint: disable=no-self-use
        return 'node'

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

    def node_type(self):
        return 'prompt'

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
                raise MissingNextDialogNodeError('next_id missing in: ' + json.dumps(dialog_def, indent=2), dialog_def, 'next_id')

            return Echo(dialog_def['id'], dialog_def['next_id'], dialog_def['message'])

        return None

    def __init__(self, node_id, next_node_id, message):
        super(Echo, self).__init__(node_id, next_node_id)

        self.message = message

    def node_type(self):
        return 'echo'

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

class Alert(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'alert':
            if ('next_id' in dialog_def) is False:
                raise MissingNextDialogNodeError('next_id missing in: ' + json.dumps(dialog_def, indent=2), dialog_def, 'next_id')

            return Alert(dialog_def['id'], dialog_def['next_id'], dialog_def['message'])

        return None

    def __init__(self, node_id, next_node_id, message):
        super(Alert, self).__init__(node_id, next_node_id)

        self.message = message

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'alert-continue'

        return transition

    def node_type(self):
        return 'alert'

    def actions(self):
        return[{
            'type': 'alert',
            'message': self.message
        }]

class End(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'end':
            return End(dialog_def['id'], None)

        return None

    def node_type(self):
        return 'end'

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

    def next_nodes(self):
        return []

class Begin(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'begin':
            return Begin(dialog_def['id'], dialog_def['next_id'])

        return None

    def node_type(self):
        return 'begin'

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

    def node_type(self):
        return 'pause'

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

    def node_type(self):
        return 'if'

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

            return LoopAction(dialog_def['id'], dialog_def['next_id'], dialog_def['iterations'], dialog_def['loop_id'])

        return None

class WhileAction(BaseNode):
    def __init__(self, action_id, action_type, test, actions):
        super(WhileAction, self).__init__(action_id, action_type)

        self.test = test
        self.actions = actions

    def node_type(self):
        return 'while'

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
            transition = DialogTransition(new_state_id=None)

            transition.metadata['reason'] = 'dialog-error'
            transition.metadata['error'] = traceback.format_exc()

            return transition


        return None

    def actions(self): # nosec
        code = compile(self.actions_script, '<string>', 'exec')

        custom_actions = []

        eval(code, {}, {'definition': self.definition, 'actions': custom_actions}) # pylint: disable=eval-used

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

    def node_type(self):
        return 'branch-prompt'

    def next_nodes(self):
        nodes = []

        if self.invalid_response_node_id is not None:
            nodes.append((self.invalid_response_node_id, 'Invalid Response'))

        if self.timeout_node_id is not None:
            nodes.append((self.timeout_node_id, 'Response Timed Out'))

        for pattern_action in self.pattern_actions:
            nodes.append((pattern_action['action'], 'Response Matched Pattern: ' + pattern_action['pattern']))

        return nodes

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

                    transition.metadata['exit_actions'] = [{
                        'type': 'store-value',
                        'key': self.node_id,
                        'value': response
                    }]

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

    def node_type(self):
        return 'external-choice'

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

    def node_type(self):
        return 'random-branch'

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

class Interrupt(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'interrupt':
            interrupt_node = Interrupt(dialog_def['id'], dialog_def['match_patterns'], dialog_def['next_id'])

            return interrupt_node

        return None

    def __init__(self, node_id, match_patterns, next_node_id):
        super(Interrupt, self).__init__(node_id, next_node_id)

        if match_patterns is None:
            self.match_patterns = []
        else:
            self.match_patterns = match_patterns

    def node_type(self):
        return 'interrupt'

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        dialog.push_value('django_dialog_engine_interrupt_node_stack', last_transition.prior_state_id)

        transition = DialogTransition(new_state_id=self.next_node_id)

        transition.metadata['reason'] = 'interrupt-continue'

        return transition

    def actions(self):
        return []

    def matches(self, response):
        if response is None:
            return None

        for match_pattern in self.match_patterns:
            if re.search(match_pattern, response) is not None:
                return match_pattern

        return None

class InterruptResume(BaseNode):
    @staticmethod
    def parse(dialog_def):
        if dialog_def['type'] == 'interrupt-resume':
            interrupt_resume_node = InterruptResume(dialog_def['id'], dialog_def['force_top'])

            return interrupt_resume_node

        return None

    def __init__(self, node_id, force_top):
        super(InterruptResume, self).__init__(node_id, node_id)

        if force_top is None:
            self.force_top = False
        else:
            self.force_top = force_top

    def node_type(self):
        return 'interrupt-resume'

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

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


class HttpResponseBranch(BaseNode): # pylint: disable=too-many-instance-attributes
    @staticmethod
    def parse(dialog_def): # pylint: disable=too-many-branches
        if dialog_def['type'] == 'http-response':
            prompt_node = HttpResponseBranch(dialog_def['id'], dialog_def['url'], dialog_def['actions'])

            if 'no_match' in dialog_def:
                prompt_node.invalid_response_node_id = dialog_def['no_match']

            if 'timeout' in dialog_def:
                prompt_node.timeout = dialog_def['timeout']

            if 'timeout_iterations' in dialog_def:
                prompt_node.timeout_iterations = dialog_def['timeout_iterations']

            if 'timeout_node_id' in dialog_def:
                prompt_node.timeout_node_id = dialog_def['timeout_node_id']

            if 'method' in dialog_def:
                prompt_node.method = dialog_def['method']
            else:
                prompt_node.method = 'GET'

            if 'headers' in dialog_def:
                prompt_node.headers = dialog_def['headers']
            else:
                prompt_node.headers = []

            if 'parameters' in dialog_def:
                prompt_node.parameters = dialog_def['parameters']
            else:
                prompt_node.parameters = []

            if 'pattern_matcher' in dialog_def:
                prompt_node.pattern_matcher = dialog_def['pattern_matcher']
            else:
                prompt_node.pattern_matcher = 're'

            return prompt_node

        return None

    def __init__(self, node_id, url, actions, invalid_response_node_id=None, timeout=300, timeout_node_id=None, timeout_iterations=None, method='GET', headers=None, parameters=None, pattern_matcher='re'): # pylint: disable=too-many-arguments
        super(HttpResponseBranch, self).__init__(node_id, node_id)

        if headers is None:
            headers = []

        if parameters is None:
            parameters = []

        self.url = url

        self.invalid_response_node_id = invalid_response_node_id

        if actions is None:
            self.pattern_actions = []
        else:
            self.pattern_actions = actions

        self.timeout = timeout
        self.timeout_node_id = timeout_node_id
        self.timeout_iterations = timeout_iterations

        self.method = method
        self.headers = headers
        self.parameters = parameters
        self.pattern_matcher = pattern_matcher

    def next_nodes(self):
        nodes = []

        if self.invalid_response_node_id is not None:
            nodes.append((self.invalid_response_node_id, 'Invalid Response'))

        if self.timeout_node_id is not None:
            nodes.append((self.timeout_node_id, 'Response Timed Out'))

        for pattern_action in self.pattern_actions:
            nodes.append((pattern_action['action'], 'Response Matched Pattern: ' + pattern_action['pattern']))

        return nodes


    def node_type(self):
        return 'http-response'

    def evaluate(self, dialog, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-arguments, too-many-return-statements, too-many-branches, too-many-locals, too-many-statements
        if extras is None:
            extras = {}

        if logger is None:
            logger = fetch_default_logger()

        parameters = {}

        for param in self.parameters:
            tokens = param.split('=', 1)

            if len(tokens) > 1:
                parameters[tokens[0]] = tokens[1]

        headers = {
            'User-Agent': 'Django Dialog Engine'
        }

        for header in self.headers:
            tokens = header.split('=', 1)

            if len(tokens) > 1:
                headers[tokens[0]] = tokens[1]

        response = None

        try:
            if self.method == 'POST':
                if self.timeout_node_id is not None:
                    response = requests.post(self.url, headers=headers, data=parameters, timeout=self.timeout)
                else:
                    response = requests.post(self.url, headers=headers, data=parameters)
            else:
                if self.timeout_node_id is not None:
                    response = requests.get(self.url, headers=headers, data=parameters, timeout=self.timeout)
                else:
                    response = requests.get(self.url, headers=headers, data=parameters)

            if response.status_code >= 200 and response.status_code < 300: # Valid response
                matched_action = None

                if self.pattern_matcher == 're':
                    for action in self.pattern_actions:
                        if re.search(action['pattern'], response.text) is not None:
                            matched_action = action

                elif self.pattern_matcher == 'jsonpath':
                    for action in self.pattern_actions:
                        parser = jsonpath_ng_parse(action['pattern'])

                        matches = list(parser.find(response.json()))

                        if len(matches) > 0: # pylint: disable=len-as-condition
                            matched_action = action

                elif self.pattern_matcher == 'xpath':
                    for action in self.pattern_actions:
                        tree = lxml.html.fromstring(response.content)

                        matches = tree.xpath(action['pattern'])

                        if matches:
                            matched_action = action

                if matched_action is not None:
                    transition = DialogTransition(new_state_id=matched_action['action'])

                    transition.metadata['reason'] = 'valid-response'
                    transition.metadata['url'] = self.url
                    transition.metadata['method'] = self.method
                    transition.metadata['parameters'] = parameters
                    transition.metadata['headers'] = headers
                    transition.metadata['http-status-code'] = response.status_code
                    transition.metadata['response'] = response.text
                    transition.metadata['actions'] = self.pattern_actions

                    return transition

            if self.invalid_response_node_id is not None:
                transition = DialogTransition(new_state_id=self.invalid_response_node_id)

                transition.metadata['reason'] = 'no-match'
                transition.metadata['url'] = self.url
                transition.metadata['method'] = self.method
                transition.metadata['parameters'] = parameters
                transition.metadata['headers'] = headers
                transition.metadata['http-status-code'] = response.status_code
                transition.metadata['response'] = response.text
                transition.metadata['actions'] = self.pattern_actions

                transition.refresh = True

                return transition
        except requests.exceptions.Timeout:
            transition = DialogTransition(new_state_id=self.timeout_node_id)
            transition.refresh = True

            transition.metadata['reason'] = 'timeout'
            transition.metadata['timeout_duration'] = self.timeout

            return transition
        except: # pylint: disable=bare-except
            traceback.print_exc()

            transition = DialogTransition(new_state_id=self.invalid_response_node_id)
            transition.refresh = True

            transition.metadata['reason'] = 'error'
            transition.metadata['error'] = traceback.format_exc()

            return transition

        return None

    def actions(self):
        return[]
