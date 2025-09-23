# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import json

import objectpath

from six import _print as print

from django.core.management.base import BaseCommand

from ...models import DialogScript

class Command(BaseCommand):
    help = 'Queries DialogScript objects for nodes matching provided ObjectPath query. Reference: http://objectpath.org/reference.html'

    def add_arguments(self, parser):
        parser.add_argument('query', type=str)

    def handle(self, *args, **options): # pylint: disable=too-many-branches
        query = options['query']

        scripts = DialogScript.objects.all()

        for script in scripts:
            tree = objectpath.Tree(script.definition)

            matches = list(tree.execute(query))

            if matches:
                print('DialogScript: %s' % script.identifier)

                for found in matches:
                    print('  %s' % json.dumps(found, indent=2))
