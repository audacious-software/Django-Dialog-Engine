# pylint: disable=no-member
# -*- coding: utf-8 -*-

import json
import signal
import time

import arrow

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import DialogScript, Dialog

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

        def handler(signum, frame):
            raise Exception("Timeout!")

        signal.signal(signal.SIGALRM, handler)
            
        while dialog.is_active():
#            print('    ACTIONS: ' + str(actions))
            
            input = None
            
            for action in actions:
#                print('    ACTION: ' + json.dumps(action))
                
                if action['type'] == 'wait-for-input':
                    signal.alarm(action['timeout'])
                    
                    print('ENTER INPUT:')
                    
                    try:
                        input = raw_input()
                    except Exception:
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

            print('    PROCESS: ' + str(input))
                    
            actions = dialog.process(input)
        
        