# pylint: disable=line-too-long

import json
import re

from django.utils import timezone


class DialogError(Exception):
    pass

class DialogMachine(object):
    def __init__(self, definition, metadata=None):
        self.all_nodes = {}
        self.current_node = None
        self.start_node = None

        if metadata is None:
            metadata = {}

        self.metadata = metadata

        for node_def in definition:
            node = None

            for cls in BaseNode.__subclasses__():
                if node is None:
                    node = cls.parse(node_def)

            if node is None:
                raise DialogError('Unable to parse node definition: ' + json.dumps(node_def, indent=2))

            self.all_nodes[node.node_id] = node

            if self.current_node is None and isinstance(node, (Begin,)):
                self.current_node = node

    def advance_to(self, node_id):
        self.current_node = self.all_nodes[node_id]

    def evaluate(self, response=None, last_transition=None):
        if self.current_node is None:
            return None

        transition = self.current_node.evaluate(self, response, last_transition)

        if transition is not None:
            if transition.new_state_id in self.all_nodes:
                if ('exit_actions' in transition.metadata) is False:
                    transition.metadata['actions'] = []
                else:
                    transition.metadata['actions'] = transition.metadata['exit_actions']

                transition.metadata['actions'] += self.all_nodes[transition.new_state_id].actions()

                if transition.metadata['actions']:
                    pass
                else:
                    transition.metadata['actions'] = None

        return transition

class DialogTransition(object): # pylint: disable=too-few-public-methods
    def __init__(self, new_state_id, metadata=None):
        self.new_state_id = new_state_id

        if metadata is None:
            metadata = {}

        self.metadata = metadata


class BaseNode(object):
    def __init__(self, node_id, next_node_id=None):
        self.node_id = node_id
        self.next_node_id = next_node_id

    def evaluate(self, dialog, response=None, last_transition=None): # pylint: disable=unused-argument
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

    def evaluate(self, dialog, response=None, last_transition=None):
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
        else:
            transition = DialogTransition(new_state_id=self.node_id)

            transition.metadata['reason'] = 'prompt-init'

            return transition

        return None

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
            return Echo(dialog_def['id'], dialog_def['next_id'], dialog_def['message'])

        return None

    def __init__(self, node_id, next_node_id, message):
        super(Echo, self).__init__(node_id, next_node_id)

        self.message = message

    def evaluate(self, dialog, response=None, last_transition=None):
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

    def evaluate(self, dialog, response=None, last_transition=None):
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

    def evaluate(self, dialog, response=None, last_transition=None):
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

    def evaluate(self, dialog, response=None, last_transition=None):
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

    def evaluate(self, dialog, response=None, last_transition=None): # pylint: disable=too-many-branches
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

    def evaluate(self, dialog, response=None, last_transition=None):
        loop_count = 0

        if last_transition is not None:
            loop_count = last_transition.dialog.transitions.filter(state_id=self.node_id).count()

        if loop_count <= self.iterations:
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


class WhileAction(BaseNode):
    def __init__(self, action_id, action_type, test, actions):
        super(WhileAction, self).__init__(action_id, action_type)

        self.test = test
        self.actions = actions

def parse_dialog_definition(definition):  # pylint: disable=unused-argument
    return []
