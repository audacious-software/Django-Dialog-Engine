# pylint: disable=line-too-long, super-with-arguments

from .base_node import BaseNode

class WhileNode(BaseNode):
    def __init__(self, action_id, action_type, test, actions):
        super(WhileNode, self).__init__(action_id, action_type)

        self.test = test
        self.actions = actions

    def node_type(self):
        return 'while'
