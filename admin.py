# pylint: disable=no-member
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.contrib import admin
from django.db.models import Q

from .models import Dialog, DialogScript, DialogStateTransition

@admin.register(Dialog)
class DialogAdmin(admin.ModelAdmin):
    list_display = ('key', 'script', 'started', 'finished', 'finish_reason',)
    search_fields = ('key', 'dialog_snapshot', 'finish_reason', 'script__name',)
    list_filter = ('started', 'finished', 'finish_reason')

def clone_dialog_scripts(modeladmin, request, queryset): # pylint: disable=unused-argument
    for item in queryset:
        item.pk = None
        item.name = item.name + ' (Copy)'
        item.identifier = item.identifier + '-copy'
        item.save()

clone_dialog_scripts.short_description = "Clone selected dialog scripts"

class DialogScriptLabelFilter(admin.SimpleListFilter):
    title = 'label'

    parameter_name = 'label'

    def lookups(self, request, model_admin):
        all_labels = []

        for script in DialogScript.objects.all():
            for label in script.labels_list():
                cleaned_label = label.split('|')[-1]

                if (cleaned_label in all_labels) is False:
                    all_labels.append(cleaned_label)

        all_labels.sort()

        lookups_list = []

        for label in all_labels:
            lookups_list.append((label, label))

        return lookups_list

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset

        query = Q(labels__contains=self.value())

        query = query | Q(labels__contains=('|%s' % self.value()))

        return queryset.filter(query)

@admin.register(DialogScript)
class DialogScriptAdmin(admin.ModelAdmin):
    list_display = ('name', 'identifier', 'created', 'admin_labels',)
    search_fields = ('name', 'identifier', 'definition', 'labels',)
    list_filter = ('created', 'embeddable', DialogScriptLabelFilter,)
    actions = [clone_dialog_scripts]

@admin.register(DialogStateTransition)
class DialogStateTransitionAdmin(admin.ModelAdmin):
    list_display = ('dialog', 'when', 'state_id', 'prior_state_id')
    list_filter = ('when',)
