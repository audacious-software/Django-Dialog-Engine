# -*- coding: utf-8 -*-
# from __future__ import unicode_literals

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from .models import DialogScript

@staff_member_required
def dashboard_dialog_scripts(request):
    context = {}

    context['dialogs'] = DialogScript.objects.all().order_by('name')

    return render(request, 'dashboard/dashboard_dialog_scripts.html', context=context)
