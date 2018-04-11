# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from .models import Dialog, DialogScript, DialogStateTransition

@admin.register(Dialog)
class DialogAdmin(admin.ModelAdmin):
    list_display = ('script', 'started', 'finished', 'finish_reason',)
    search_fields = ('dialog_snapshot', 'finish_reason', 'script',)
    list_filter = ('started', 'finished', 'finish_reason')

@admin.register(DialogScript)
class DialogScriptAdmin(admin.ModelAdmin):
    list_display = ('name', 'created',)
    search_fields = ('name', 'description',)
    list_filter = ('created',)

@admin.register(DialogStateTransition)
class DialogStateTransitionAdmin(admin.ModelAdmin):
    list_display = ('dialog', 'when', 'state_id', 'prior_state_id')
    list_filter = ('when',)
