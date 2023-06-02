# pylint: disable=no-member, line-too-long, len-as-condition
# -*- coding: utf-8 -*-

from __future__ import print_function

from django.core.management.base import BaseCommand

from ...models import DialogScript

class Command(BaseCommand):
    help = 'Validates that dialog scripts are configured correctly.'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options): # pylint: disable=too-many-branches
        scripts = DialogScript.objects.all()

        for script in scripts:
            if script.is_active():
                issues = script.issues()

                if len(issues) > 0:
                    if len(issues) == 1:
                        print('%s: %d issue...' % (script.name, len(issues)))
                    else:
                        print('%s: %d issues...' % (script.name, len(issues)))

                    for issue in issues:
                        print('  [%s] %s' % (issue[0], issue[1]))
