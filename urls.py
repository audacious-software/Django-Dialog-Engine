# pylint: disable=line-too-long

import sys

if sys.version_info[0] > 2:
    from django.urls import re_path as url # pylint: disable=no-name-in-module
else:
    from django.conf.urls import url

from .views import dashboard_dialog_scripts # pylint: disable=wrong-import-position

urlpatterns = [
    url(r'^dashboard/dialog/scripts$', dashboard_dialog_scripts, name='dashboard_dialog_scripts'),
]
