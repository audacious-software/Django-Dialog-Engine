# pylint: disable=line-too-long, no-member

import json

from django.test import TestCase
from django.utils import timezone

from ..models import Dialog

class InterruptsTestCase(TestCase):
    def setUp(self):
        with open('django_dialog_engine/tests/scripts/interrupt_script.json', encoding='utf8') as definition_file:
            dialog_definition = json.load(definition_file)

            self.dialog_no_interrupt = Dialog.objects.create(dialog_snapshot=dialog_definition, started=timezone.now())
            self.dialog_with_interrupt = Dialog.objects.create(dialog_snapshot=dialog_definition, started=timezone.now())
            self.dialog_with_interrupt_force_top = Dialog.objects.create(dialog_snapshot=dialog_definition, started=timezone.now())

        with open('django_dialog_engine/tests/scripts/interrupt_script_nested.json', encoding='utf8') as nested_file:
            nested_definition = json.load(nested_file)

            self.dialog_with_interrupt_nested = Dialog.objects.create(dialog_snapshot=nested_definition, started=timezone.now())

    def test_interrupts_working_no_interrupt(self): # pylint: disable=invalid-name
        self.assertIsNone(self.dialog_no_interrupt.current_state_id())

        self.assertIsNotNone(self.dialog_no_interrupt.started)

        self.assertIsNone(self.dialog_no_interrupt.finished)

        self.dialog_no_interrupt.process(None)

        self.assertEqual(self.dialog_no_interrupt.current_state_id(), 'echo-1')

        self.dialog_no_interrupt.process(None)

        self.assertEqual(self.dialog_no_interrupt.current_state_id(), 'test-variable')

        self.dialog_no_interrupt.process('testing 123')

        self.assertEqual(self.dialog_no_interrupt.current_state_id(), 'dialog-end')

        self.dialog_no_interrupt.process(None)

        self.assertEqual(self.dialog_no_interrupt.finish_reason, 'dialog_concluded')

        self.assertIsNotNone(self.dialog_no_interrupt.finished)

    def test_interrupts_working_with_interrupt(self): # pylint: disable=invalid-name
        self.assertIsNone(self.dialog_with_interrupt.current_state_id())

        self.assertIsNotNone(self.dialog_with_interrupt.started)

        self.assertIsNone(self.dialog_with_interrupt.finished)

        self.dialog_with_interrupt.process(None)

        self.assertEqual(self.dialog_with_interrupt.current_state_id(), 'echo-1')

        self.dialog_with_interrupt.process(None)

        self.assertEqual(self.dialog_with_interrupt.current_state_id(), 'test-variable')

        self.dialog_with_interrupt.process('foo should trigger interrupt')

        self.assertEqual(self.dialog_with_interrupt.current_state_id(), 'interrupt-start')

        self.dialog_with_interrupt.process(None)

        self.assertEqual(self.dialog_with_interrupt.current_state_id(), 'interrupt-message')

        self.dialog_with_interrupt.process(None)

        self.assertEqual(self.dialog_with_interrupt.current_state_id(), 'interrupt-wait')

        self.dialog_with_interrupt.process(None)

        self.assertEqual(self.dialog_with_interrupt.current_state_id(), 'interrupt-wait')

        self.dialog_with_interrupt.process('testing 123')

        self.assertEqual(self.dialog_with_interrupt.current_state_id(), 'interrupt-resume')

        self.dialog_with_interrupt.process(None)

        self.assertEqual(self.dialog_with_interrupt.current_state_id(), 'test-variable')

        self.dialog_with_interrupt.process('testing')

        self.assertEqual(self.dialog_with_interrupt.current_state_id(), 'dialog-end')

        self.dialog_with_interrupt.process(None)

        self.assertEqual(self.dialog_with_interrupt.finish_reason, 'dialog_concluded')

        self.assertIsNotNone(self.dialog_with_interrupt.finished)

    def test_interrupts_working_with_nested_interrupt_force_top(self): # pylint: disable=invalid-name
        self.assertIsNone(self.dialog_with_interrupt_force_top.current_state_id())

        self.assertIsNotNone(self.dialog_with_interrupt_force_top.started)

        self.assertIsNone(self.dialog_with_interrupt_force_top.finished)

        self.dialog_with_interrupt_force_top.process(None)

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'echo-1')

        self.dialog_with_interrupt_force_top.process(None)

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'test-variable')

        self.dialog_with_interrupt_force_top.process('foo should trigger interrupt')

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'interrupt-start')

        self.dialog_with_interrupt_force_top.process(None)

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'interrupt-message')

        self.dialog_with_interrupt_force_top.process(None)

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'interrupt-wait')

        self.dialog_with_interrupt_force_top.process(None)

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'interrupt-wait')

        self.dialog_with_interrupt_force_top.process('bar should also trigger interrupt')

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'interrupt-start')

        self.dialog_with_interrupt_force_top.process(None)

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'interrupt-message')

        self.dialog_with_interrupt_force_top.process(None)

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'interrupt-wait')

        self.dialog_with_interrupt_force_top.process(None)

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'interrupt-wait')

        self.dialog_with_interrupt_force_top.process('testing')

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'interrupt-resume')

        self.dialog_with_interrupt_force_top.process(None)

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'test-variable')

        self.dialog_with_interrupt_force_top.process('testing')

        self.assertEqual(self.dialog_with_interrupt_force_top.current_state_id(), 'dialog-end')

        self.dialog_with_interrupt_force_top.process(None)

        self.assertEqual(self.dialog_with_interrupt_force_top.finish_reason, 'dialog_concluded')

        self.assertIsNotNone(self.dialog_with_interrupt_force_top.finished)

    def test_interrupts_working_with_nested_interrupt_nested(self): # pylint: disable=invalid-name
        self.assertIsNone(self.dialog_with_interrupt_nested.current_state_id())

        self.assertIsNotNone(self.dialog_with_interrupt_nested.started)

        self.assertIsNone(self.dialog_with_interrupt_nested.finished)

        self.dialog_with_interrupt_nested.process(None)

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'echo-1')

        self.dialog_with_interrupt_nested.process(None)

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'test-variable')

        self.dialog_with_interrupt_nested.process('foo should trigger interrupt')

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'interrupt-start')

        self.dialog_with_interrupt_nested.process(None)

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'interrupt-message')

        self.dialog_with_interrupt_nested.process(None)

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'interrupt-wait')

        self.dialog_with_interrupt_nested.process(None)

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'interrupt-wait')

        self.dialog_with_interrupt_nested.process('bar should also trigger interrupt')

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'interrupt-start')

        self.dialog_with_interrupt_nested.process(None)

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'interrupt-message')

        self.dialog_with_interrupt_nested.process(None)

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'interrupt-wait')

        self.dialog_with_interrupt_nested.process(None)

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'interrupt-wait')

        self.dialog_with_interrupt_nested.process('testing')

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'interrupt-resume')

        self.dialog_with_interrupt_nested.process(None)

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'interrupt-wait')

        self.dialog_with_interrupt_nested.process('testing')

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'interrupt-resume')

        self.dialog_with_interrupt_nested.process(None)

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'test-variable')

        self.dialog_with_interrupt_nested.process('testing')

        self.assertEqual(self.dialog_with_interrupt_nested.current_state_id(), 'dialog-end')

        self.dialog_with_interrupt_nested.process(None)

        self.assertEqual(self.dialog_with_interrupt_nested.finish_reason, 'dialog_concluded')

        self.assertIsNotNone(self.dialog_with_interrupt_nested.finished)
