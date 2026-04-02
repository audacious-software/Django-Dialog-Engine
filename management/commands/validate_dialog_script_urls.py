# pylint: disable=no-member, line-too-long, len-as-condition
# -*- coding: utf-8 -*-

import time

import requests

from django.core.management.base import BaseCommand

from ...models import DialogScript

class Command(BaseCommand):
    help = 'Validates that dialog scripts are configured correctly.'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options): # pylint: disable=too-many-branches
        scripts = DialogScript.objects.all()

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0'
        }

        for script in scripts:
            urls = script.fetch_urls()

            for url in urls:
                time.sleep(1.0)
                try:
                    resp = requests.get(url, headers=headers, timeout=30)

                    if resp.status_code < 200 or resp.status_code >= 300:
                        print('%s: %s received status code %s' % (script.name, url, resp.status_code))
                except Exception as ex: # pylint: disable=broad-exception-caught
                    print('%s: %s encountered an error: %s' % (script.name, url, ex))
