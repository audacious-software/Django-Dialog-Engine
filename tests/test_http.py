# pylint: disable=line-too-long, no-member

import io
import json

from django.test import TestCase
from django.utils import timezone

from ..models import Dialog

class HttpTestCase(TestCase):
    def setUp(self):
        with io.open('django_dialog_engine/tests/scripts/http_script.json', encoding='utf8') as definition_file:
            dialog_definition = json.load(definition_file)

            self.dialog_http = Dialog.objects.create(dialog_snapshot=dialog_definition, started=timezone.now())

        with io.open('django_dialog_engine/tests/scripts/http_script_fail.json', encoding='utf8') as fail_file:
            fail_definition = json.load(fail_file)

            self.dialog_http_fail = Dialog.objects.create(dialog_snapshot=fail_definition, started=timezone.now())

    def test_http_success(self):
        self.assertIsNone(self.dialog_http.current_state_id())

        self.assertIsNotNone(self.dialog_http.started)

        self.assertIsNone(self.dialog_http.finished)

        self.dialog_http.process(None)

        self.assertEqual(self.dialog_http.current_state_id(), 'echo-1')

        self.dialog_http.process(None)

        self.assertEqual(self.dialog_http.current_state_id(), 'get-test-re')

        self.dialog_http.process(None)

        self.assertEqual(self.dialog_http.current_state_id(), 'get-success-re')

        self.dialog_http.process(None)

        self.assertEqual(self.dialog_http.current_state_id(), 'get-test-jsonpath')

        self.dialog_http.process(None)

        self.assertEqual(self.dialog_http.current_state_id(), 'get-success-jsonpath')

        self.dialog_http.process(None)

        self.assertEqual(self.dialog_http.current_state_id(), 'dialog-end')

        self.dialog_http.process(None)

        self.assertEqual(self.dialog_http.finish_reason, 'dialog_concluded')

        self.assertIsNotNone(self.dialog_http.finished)

    def test_http_failure(self):
        self.assertIsNone(self.dialog_http_fail.current_state_id())

        self.assertIsNotNone(self.dialog_http_fail.started)

        self.assertIsNone(self.dialog_http_fail.finished)

        self.dialog_http_fail.process(None)

        self.assertEqual(self.dialog_http_fail.current_state_id(), 'echo-1')

        self.dialog_http_fail.process(None)

        self.assertEqual(self.dialog_http_fail.current_state_id(), 'get-test-re')

        self.dialog_http_fail.process(None)

        self.assertEqual(self.dialog_http_fail.current_state_id(), 'get-failed-re')

        self.dialog_http_fail.process(None)

        self.assertEqual(self.dialog_http_fail.current_state_id(), 'get-test-jsonpath')

        self.dialog_http_fail.process(None)

        self.assertEqual(self.dialog_http_fail.current_state_id(), 'get-failed-jsonpath')

        self.dialog_http_fail.process(None)

        self.assertEqual(self.dialog_http_fail.current_state_id(), 'dialog-end')

        self.dialog_http_fail.process(None)

        self.assertEqual(self.dialog_http_fail.finish_reason, 'dialog_concluded')

        self.assertIsNotNone(self.dialog_http_fail.finished)
