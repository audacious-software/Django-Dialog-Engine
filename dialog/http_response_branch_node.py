# pylint: disable=line-too-long, super-with-arguments

import re
import traceback

import lxml # nosec
import requests

from jsonpath_ng.ext import parse as jsonpath_ng_parse

from .base_node import BaseNode, fetch_default_logger
from .dialog_machine import DialogTransition

class HttpResponseBranchNode(BaseNode): # pylint: disable=too-many-instance-attributes
    @staticmethod
    def parse(dialog_def): # pylint: disable=too-many-branches
        if dialog_def['type'] == 'http-response':
            prompt_node = HttpResponseBranchNode(dialog_def['id'], dialog_def['url'], dialog_def['actions'])

            if 'no_match' in dialog_def:
                prompt_node.invalid_response_node_id = dialog_def['no_match']

            timeout = dialog_def.get('timeout', None)
            timeout_node_id = dialog_def.get('timeout_node_id', None)

            if timeout is not None and timeout_node_id is not None:
                prompt_node.timeout = timeout
                prompt_node.timeout_node_id = timeout_node_id

                if 'timeout_iterations' in dialog_def:
                    prompt_node.timeout_iterations = dialog_def['timeout_iterations']

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
        super(HttpResponseBranchNode, self).__init__(node_id, node_id)

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

    def prefix_nodes(self, prefix):
        super().prefix_nodes(prefix) # pylint: disable=missing-super-argument

        if self.timeout_node_id is not None:
            self.timeout_node_id = prefix + self.timeout_node_id

        if self.invalid_response_node_id is not None:
            self.invalid_response_node_id = prefix + self.invalid_response_node_id

        for action in self.pattern_actions:
            action['action'] = prefix + action['action']

    def node_definition(self):
        node_def = super().node_definition() # pylint: disable=missing-super-argument

        if 'next_id' in node_def:
            del node_def['next_id']

        if self.timeout is not None:
            node_def['timeout'] = self.timeout

        if self.timeout_node_id is not None:
            node_def['timeout_node_id'] = self.timeout_node_id

        if self.timeout_iterations is not None:
            node_def['timeout_iterations'] = self.timeout_iterations

        node_def['method'] = self.method
        node_def['headers'] = self.headers
        node_def['parameters'] = self.parameters
        node_def['pattern_matcher'] = self.pattern_matcher

        node_def['actions'] = self.pattern_actions

        return node_def

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
                    response = requests.post(self.url, headers=headers, data=parameters, timeout=300)
            else:
                if self.timeout_node_id is not None:
                    response = requests.get(self.url, headers=headers, data=parameters, timeout=self.timeout)
                else:
                    response = requests.get(self.url, headers=headers, data=parameters, timeout=300)

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
