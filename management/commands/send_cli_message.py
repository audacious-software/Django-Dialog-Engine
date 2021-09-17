# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

from __future__ import print_function

from builtins import str # pylint: disable=redefined-builtin

import importlib
import json
import logging
import os

from future import standard_library

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from ...models import Dialog

standard_library.install_aliases()

def process(dialog, message, extras=None, skip_extensions=False):
    if extras is None:
        extras = {}

    processed = False

    if skip_extensions is False:
        for app in settings.INSTALLED_APPS:
            if processed is False:
                try:
                    app_dialog_api = importlib.import_module(app + '.dialog_api')

                    app_dialog_api.process(dialog, message, extras=extras)

                    processed = True
                except ImportError:
                    pass
                except AttributeError:
                    pass

    if processed is False:
        actions = dialog.process(message, extras=extras)

        if actions is None:
            actions = []

        for action in actions:
            if action['type'] == 'echo':
                print(action['message'])


class Command(BaseCommand):
    help = 'Creates a new dialog from a provided JSON definition and executes it via the command line interface'

    def add_arguments(self, parser):
        parser.add_argument('dialog_user_id', type=str)
        parser.add_argument('dialog_script_path', type=str)
        parser.add_argument('message', type=str)
        parser.add_argument('--skip_extensions', action='store_true')

    def handle(self, *args, **options): # pylint: disable=too-many-branches
        dialog_user_id = options['dialog_user_id']
        dialog_script_path = options['dialog_script_path']

        logging.getLogger('db').setLevel(logging.ERROR)

        extras = {}

        try:
            extras = settings.DDE_BOTIUM_EXTRAS(dialog_user_id)
        except AttributeError:
            pass

        filename = os.path.basename(os.path.normpath(dialog_script_path))

        key = slugify(filename + '-' + dialog_user_id)

        active_dialog = None

        active_dialog = Dialog.objects.filter(key=key, finished=None).first()

        if active_dialog is None:
            if options['skip_extensions'] is False:
                for app in settings.INSTALLED_APPS:
                    if active_dialog is None:
                        try:
                            app_dialog_api = importlib.import_module(app + '.dialog_api')

                            active_dialog = app_dialog_api.create_dialog_from_path(dialog_script_path, dialog_key=key)
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

        process(active_dialog, options['message'], extras=extras, skip_extensions=options['skip_extensions'])

        last_transition = active_dialog.transitions.order_by('-when').first()

        process(active_dialog, None, extras=extras, skip_extensions=options['skip_extensions'])

        nudge_transition = active_dialog.transitions.order_by('-when').first()

        while nudge_transition.pk != last_transition.pk:
            last_transition = nudge_transition

            process(active_dialog, None, extras=extras, skip_extensions=options['skip_extensions'])

            nudge_transition = active_dialog.transitions.order_by('-when').first()
