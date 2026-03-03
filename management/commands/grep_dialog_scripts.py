# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import json

import jsonpath_ext as jsonpath

import six

from django.core.management.base import BaseCommand

from ...models import DialogScript

class Command(BaseCommand):
    help = 'Queries DialogScript objects for nodes matching provided JSONPatH query.'

    def add_arguments(self, parser):
        parser.add_argument('query', type=str)

    def handle(self, *args, **options): # pylint: disable=too-many-branches
        query = options['query'].replace('\\!', '!')

        scripts = DialogScript.objects.all()

        for script in scripts:
            matches = jsonpath.find(query, script.definition)

            if matches:
                six.print_('DialogScript: %s' % script.identifier)

                for found in matches:
                    six.print_('  %s' % json.dumps(found.value, indent=2))
