# pylint: disable=useless-object-inheritance

import logging
import sys

class DialogError(Exception):
    pass

class MissingNextDialogNodeError(DialogError):
    def __init__(self, message, container, key):
        super(DialogError, self).__init__(message) # pylint: disable=bad-super-call

        self.container = container
        self.key = key

class BaseNode(object):
    def __init__(self, node_id, next_node_id=None):
        self.node_id = node_id
        self.next_node_id = next_node_id

        self.node_name = node_id

        self.definition = None

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

def fetch_default_logger():
    logger = logging.getLogger('django-dialog-engine')
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger

class DialogTransition(object): # pylint: disable=too-few-public-methods
    def __init__(self, new_state_id, metadata=None):
        self.new_state_id = new_state_id

        self.refresh = False

        if metadata is None:
            metadata = {}

        self.metadata = metadata
