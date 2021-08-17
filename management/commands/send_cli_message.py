# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

from __future__ import print_function

from builtins import str # pylint: disable=redefined-builtin

import importlib
import json
import os

from future import standard_library

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import Dialog

standard_library.install_aliases()

class Command(BaseCommand):
    help = 'Creates a new dialog from a provided JSON definition and executes it via the command line interface'

    def add_arguments(self, parser):
        parser.add_argument('dialog_user_id', type=str)
        parser.add_argument('dialog_script_path', type=str)
        parser.add_argument('message', type=str)

    def handle(self, *args, **options): # pylint: disable=too-many-branches
        dialog_user_id = options['dialog_user_id']
        dialog_script_path = options['dialog_script_path']

        filename = os.path.basename(os.path.normpath(dialog_script_path))

        key = filename + '-' + dialog_user_id

        active_dialog = None

        active_dialog = Dialog.objects.filter(key=key, finished=None).first()

        if active_dialog is None:
            for app in settings.INSTALLED_APPS:
                if active_dialog is None:
                    try:
                        app_dialog_api = importlib.import_module(app + '.dialog_api')

                        active_dialog = app_dialog_api.create_dialog_from_path(dialog_script_path)
                        active_dialog.key = key
                        active_dialog.started = timezone.now()
                        active_dialog.save()
                    except ImportError:
                        pass
                    except AttributeError:
                        pass

            if active_dialog is None:
                dialog_script = json.load(open(dialog_script_path))

                active_dialog = Dialog.objects.create(key=key, dialog_snapshot=dialog_script, started=timezone.now())

        actions = active_dialog.process(options['message'])

        if actions is None:
            actions = []

        for action in actions:
            if action['type'] == 'echo':
                print(action['message'])

        last_transition = active_dialog.transitions.order_by('-when').first()

        actions = active_dialog.process(None)

        if actions is None:
            actions = []

        for action in actions:
            if action['type'] == 'echo':
                print(action['message'])

        nudge_transition = active_dialog.transitions.order_by('-when').first()

        while nudge_transition.pk != last_transition.pk:
            last_transition = nudge_transition

            actions = active_dialog.process(None)

            if actions is None:
                actions = []

            for action in actions:
                if action['type'] == 'echo':
                    print(action['message'])

            nudge_transition = active_dialog.transitions.order_by('-when').first()
