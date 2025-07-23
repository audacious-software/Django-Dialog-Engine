# pylint: disable=line-too-long, useless-object-inheritance, super-with-arguments

from builtins import object # pylint: disable=redefined-builtin

import copy
import importlib
import logging
import json

from django.conf import settings

from .base_node import BaseNode, MissingNextDialogNodeError, DialogError, DialogTransition

MISSING_NEXT_NODE_KEY = 'django-dialog-engine-missing-next-node-end'

class DialogMachine(object):
    def __init__(self, definition, metadata=None, django_object=None):
        from .begin_node import BeginNode # pylint: disable=import-outside-toplevel
        from .end_node import EndNode # pylint: disable=import-outside-toplevel

        definition = copy.deepcopy(definition)

        self.all_nodes = {}
        self.current_node = None
        self.start_node = None

        self.django_object = django_object

        if metadata is None:
            metadata = {}

        self.metadata = metadata

        for app in settings.INSTALLED_APPS:
            try:
                importlib.import_module(app + '.dialog_api')
            except ImportError:
                pass
            except AttributeError:
                pass

        for node_def in definition:
            node = None

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

                            end_node = EndNode.parse(end_node_def)

                            end_node.definition = end_node_def

                            self.all_nodes[end_node.node_id] = end_node

                        missing_node.container[missing_node.key] = MISSING_NEXT_NODE_KEY

                        node = cls.parse(node_def)

                    if node is not None and 'name' in node_def:
                        node.node_name = node_def['name']
                        node.definition = node_def

            if node is None:
                raise DialogError('Unable to parse node definition: ' + json.dumps(node_def, indent=2))

            self.all_nodes[node.node_id] = node

            if self.current_node is None and isinstance(node, BeginNode):
                self.current_node = node

    def advance_to(self, node_id):
        try:
            self.current_node = self.all_nodes[node_id]
        except KeyError:
            pass # Cannot continue - stay in same place.

    def evaluate(self, response=None, last_transition=None, extras=None, logger=None): # pylint: disable=too-many-branches
        from .interrupt_node import InterruptNode # pylint: disable=import-outside-toplevel
        from .time_elapsed_interrupt_node import TimeElapsedInterruptNode # pylint: disable=import-outside-toplevel

        if extras is None:
            extras = {}

        if self.current_node is None:
            return None

        if logger is None:
            logger = logging.getLogger()

        for key, node in self.all_nodes.items(): # pylint: disable=unused-variable
            if response is not None and isinstance(node, (InterruptNode,)):
                pattern_matched = node.matches(response)

                if pattern_matched is not None:
                    transition = DialogTransition(new_state_id=node.node_id)

                    transition.metadata['reason'] = 'interrupt'
                    transition.metadata['pattern'] = 'pattern_matched'
                    transition.metadata['response'] = response
                    transition.metadata['actions'] = []

                    return transition
            elif isinstance(node, (TimeElapsedInterruptNode,)):
                if node.should_fire(last_transition):
                    transition = DialogTransition(new_state_id=node.node_id)

                    transition.metadata['reason'] = 'time-elapsed-interrupt'
                    transition.metadata['hours_elapsed'] = node.hours_elapsed
                    transition.metadata['minutes_elapsed'] = node.minutes_elapsed

                    return transition

        logger.debug('Evaluating current node: %s -- Response: %s -- Extras: %s -- Logger: %s', self.current_node, response, len(extras), logger)
        transition = self.current_node.evaluate(self, response, last_transition, extras, logger)
        logger.debug('Evaluation complete for %s -- %s', self.current_node, transition)

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

        logger.debug('Returning transition: %s from %s', transition, self.current_node)

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

    def prefix_nodes(self, prefix):
        node_keys = list(self.all_nodes.keys())

        for key in node_keys:
            new_key = prefix + key

            node = self.all_nodes.pop(key)
            node.prefix_nodes(prefix)

            self.all_nodes[new_key] = node

    def dialog_definition(self):
        nodes_definitions = []

        for node in self.nodes():
            nodes_definitions.append(node.node_definition())

        return nodes_definitions
