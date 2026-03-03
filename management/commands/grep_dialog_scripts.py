# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import json

import jsonpath

import six

from django.core.management.base import BaseCommand

from ...models import DialogScript

class Command(BaseCommand):
    help = 'Queries DialogScript objects for nodes matching provided JSONPatH query.'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options): # pylint: disable=too-many-branches
        query = six.moves.input('Enter your JSONPath query: ')

        scripts = DialogScript.objects.all()

        for script in scripts:
            matches = []

            try:
                matches = jsonpath.findall(query, script.definition)
            except AttributeError:
                matches = jsonpath.jsonpath(script.definition, query)

            if matches:
                six.print_('DialogScript: %s' % script.identifier)

                for found in matches:
                    six.print_('  %s' % json.dumps(found, indent=2))
