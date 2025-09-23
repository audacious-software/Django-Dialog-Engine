# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

from builtins import str # pylint: disable=redefined-builtin
from builtins import input # pylint: disable=redefined-builtin

import io
import json
import signal
import time

from six import print_ as print

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...dialog.base_node import DialogError
from ...models import DialogScript, Dialog

class Command(BaseCommand):
    help = 'Creates a new dialog from a provided JSON definition and executes it via the command line interface'

    def add_arguments(self, parser):
        parser.add_argument('dialog_json', type=str)


    def handle(self, *args, **options):
        with io.open(options['dialog_json'], encoding='utf8') as script_file:
            dialog_json = json.load(script_file)

            script = DialogScript.objects.create(name=options['dialog_json'], created=timezone.now(), definition=dialog_json)

            if script.is_valid() is False:
                script.delete()

                raise ValueError('Invalid script. Please review and try again.')

            dialog = Dialog.objects.create(script=script, started=timezone.now())

            if dialog.is_valid() is False:
                dialog.delete()

                raise ValueError('Invalid dialog. Please review and try again.')

            actions = dialog.process()

            def handler(signum, frame): # pylint: disable=unused-argument
                raise DialogError("Timeout!")

            signal.signal(signal.SIGALRM, handler)

            while dialog.is_active():
                # print('    ACTIONS: ' + str(actions))

                input_str = None

                for action in actions:
                    # print('    ACTION: ' + json.dumps(action))

                    if action['type'] == 'wait-for-input':
                        signal.alarm(action['timeout'])

                        print('ENTER INPUT:')

                        try:
                            input_str = input()
                        except: # pylint: disable=bare-except
                            break

                        signal.alarm(0)
                    elif action['type'] == 'echo':
                        print('ECHO: ' + action['message'])
                    elif action['type'] == 'pause':
                        print('PAUSE: ' + str(action['duration']))
                        time.sleep(action['duration'])
                    elif action['type'] == 'store-value':
                        print('STORE: ' + str(action['key']) + ' = ' + str(action['value']))
                    else:
                        raise DialogError('Unknown action: %s' % json.dumps(action))

                print('    PROCESS: %s' % input_str)

                actions = dialog.process(input_str)
