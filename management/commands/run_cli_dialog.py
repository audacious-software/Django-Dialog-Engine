# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

from __future__ import print_function

from builtins import str # pylint: disable=redefined-builtin
from builtins import input # pylint: disable=redefined-builtin

import json
import signal
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import DialogScript, Dialog

from future import standard_library

standard_library.install_aliases()

class Command(BaseCommand):
    help = 'Creates a new dialog from a provided JSON definition and executes it via the command line interface'

    def add_arguments(self, parser):
        parser.add_argument('dialog_json', type=str)


    def handle(self, *args, **options):
        dialog_json = json.load(open(options['dialog_json']))

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
            raise Exception("Timeout!") # pylint: disable=broad-except

        signal.signal(signal.SIGALRM, handler)

        while dialog.is_active():
#            print('    ACTIONS: ' + str(actions))

            input_str = None

            for action in actions:
#                print('    ACTION: ' + json.dumps(action))

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
                    raise Exception('Unknown action: ' + json.dumps(action))

            print('    PROCESS: ' + str(input_str))

            actions = dialog.process(input_str)
