# pylint: disable=no-member, line-too-long

import json

from django.test import TestCase
from django.utils import timezone

from ..dialog import DialogMachine, MISSING_NEXT_NODE_KEY
from ..models import Dialog

class TestMissingNextNodeCase(TestCase):
    def setUp(self):
        with open('django_dialog_engine/tests/scripts/missing_next_node.json') as definition_file:
            self.test_def = json.load(definition_file)

    def test_test_missing_next_node(self):
        machine = DialogMachine(self.test_def, {})

        self.assertIn('hello', machine.all_nodes)

        hello_node = machine.all_nodes['hello']

        self.assertIsNot(hello_node.next_node_id, None)

        self.assertEqual(hello_node.next_node_id, MISSING_NEXT_NODE_KEY)

        dialog = Dialog.objects.create(key='missing-node', dialog_snapshot=self.test_def, started=timezone.now())

        dialog.process(None)
        dialog.process(None)
        dialog.process(None)

        self.assertIsNot(dialog.finished, None)
        self.assertEqual(dialog.finish_reason, 'dialog_concluded')
