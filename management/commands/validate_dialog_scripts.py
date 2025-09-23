# pylint: disable=no-member, line-too-long, len-as-condition
# -*- coding: utf-8 -*-

import six

from django.core.management.base import BaseCommand

from ...models import DialogScript

class Command(BaseCommand):
    help = 'Validates that dialog scripts are configured correctly.'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options): # pylint: disable=too-many-branches
        scripts = DialogScript.objects.all()

        issue_count = 0

        for script in scripts:
            if script.is_active():
                issues = script.issues()

                issue_count += len(issues)

                if len(issues) > 0:
                    if len(issues) == 1:
                        six._print('%s: %d issue...' % (script.name, len(issues)))
                    else:
                        six._print('%s: %d issues...' % (script.name, len(issues)))

                    for issue in issues:
                        six._print('  [%s] %s' % (issue[0], issue[1]))

        six._print('Total issues: %s' % issue_count)
