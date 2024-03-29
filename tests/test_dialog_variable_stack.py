# pylint: disable=line-too-long, no-member

import io
import json

from django.test import TestCase
from django.utils import timezone

from ..models import Dialog

class InterruptsTestCase(TestCase):
    def setUp(self):
        with io.open('django_dialog_engine/tests/scripts/interrupt_script.json', encoding='utf8') as definition_file:
            dialog_definition = json.load(definition_file)

            self.dialog = Dialog.objects.create(dialog_snapshot=dialog_definition, started=timezone.now())

    def test_dialog_variable_stack(self):
        self.dialog.put_value('foo', 'bar')

        self.assertEqual(self.dialog.get_value('foo'), 'bar')

        self.dialog.push_value('hello', 'world')

        self.assertEqual(self.dialog.pop_value('hello'), 'world')

        self.assertIsNone(self.dialog.pop_value('hello'))
