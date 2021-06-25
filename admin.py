# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from .models import Dialog, DialogScript, DialogStateTransition

@admin.register(Dialog)
class DialogAdmin(admin.ModelAdmin):
    list_display = ('key', 'script', 'started', 'finished', 'finish_reason',)
    search_fields = ('key', 'dialog_snapshot', 'finish_reason', 'script',)
    list_filter = ('started', 'finished', 'finish_reason')

def clone_dialog_scripts(modeladmin, request, queryset): # pylint: disable=unused-argument
    for item in queryset:
        item.pk = None
        item.name = item.name + ' (Copy)'
        item.identifier = item.identifier + '-copy'
        item.save()

clone_dialog_scripts.short_description = "Clone selected dialog scripts"

@admin.register(DialogScript)
class DialogScriptAdmin(admin.ModelAdmin):
    list_display = ('name', 'identifier', 'created',)
    search_fields = ('name', 'identifier', 'definition',)
    list_filter = ('created',)
    actions = [clone_dialog_scripts]

@admin.register(DialogStateTransition)
class DialogStateTransitionAdmin(admin.ModelAdmin):
    list_display = ('dialog', 'when', 'state_id', 'prior_state_id')
    list_filter = ('when',)
