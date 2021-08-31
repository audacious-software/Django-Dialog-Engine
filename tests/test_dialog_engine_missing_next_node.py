# pylint: disable=no-member

import json

from django.test import TestCase
from django.utils import timezone

from ..dialog import DialogMachine
from ..models import Dialog

class TestMissingNextNodeCase(TestCase):
    def setUp(self):
        pass

    def test_test_missing_next_node(self):
        test_def = json.load('django_dialog_engine/tests/scripts/missing_next_node.json')

        machine = DialogMachine(test_def, {})

        self.assertIn('hello', machine.all_nodes)

        hello_node = machine.all_nodes['hello']

        self.assertIsNot(hello_node.next_node_id, None)

        self.assertEqual(len(hello_node.next_node_id), 36)

        dialog = Dialog.objects.create(key='missing-node', dialog_snapshot=test_def, started=timezone.now())

        dialog.process(None)
        dialog.process(None)
        dialog.process(None)

        self.assertIsNot(dialog.finished, None)
        self.assertEqual(dialog.finish_reason, 'dialog_concluded')
