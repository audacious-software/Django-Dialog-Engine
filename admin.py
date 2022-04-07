# pylint: disable=no-member
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django import forms

from django.contrib import admin
from django.contrib.admin.helpers import ActionForm
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

class DialogScriptArchiveFilter(admin.SimpleListFilter):
    title = 'archive status'

    parameter_name = 'archive_status'

    def lookups(self, request, model_admin):
        return (('not_archived', 'Active'), ('archived', 'Archived'),)

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset

        query = Q(labels__contains='archived')

        query = query | Q(labels__contains=('|archived'))

        if self.value() == 'not_archived':
            return queryset.exclude(query)

        return queryset.filter(query)

class DialogScriptLabelWidget(forms.widgets.TextInput):
    template_name = 'widgets/admin/django_dialog_engine_dialog_script_label.html'

class DialogScriptLabelForm(ActionForm):
    label_field = forms.CharField(
        min_length=1,
        strip=True,
        label='Label:',
        required=False,
        widget=DialogScriptLabelWidget()
    )

@admin.register(DialogScript)
class DialogScriptAdmin(admin.ModelAdmin):
    list_display = ('name', 'identifier', 'size', 'created', 'admin_labels',)
    search_fields = ('name', 'identifier', 'definition', 'labels',)
    list_filter = (DialogScriptArchiveFilter, 'created', 'embeddable', DialogScriptLabelFilter,)

    def add_label(self, request, queryset):
        label = request.POST.get('label_field', None)

        if label is not None:
            count = 0

            for script in queryset:
                if script.add_label(label):
                    count += 1

            self.message_user(request, '%d dialog script(s) updated.' % count)
        else:
            self.message_user(request, 'Please provide a label.')

    add_label.short_description = "Add label to selected dialog scripts"

    def clear_label(self, request, queryset):
        label = request.POST.get('label_field', None)

        if label is not None:
            count = 0

            for script in queryset:
                if script.clear_label(label):
                    count += 1

            self.message_user(request, '%d dialog script(s) updated.' % count)
        else:
            self.message_user(request, 'Please provide a label.')

    clear_label.short_description = "Clear label to selected dialog scripts"

    def archive_script(self, request, queryset):
        count = 0

        for script in queryset:
            if script.add_label('archived'):
                count += 1

        self.message_user(request, '%d dialog script(s) archived.' % count)

    archive_script.short_description = "Archive selected dialog scripts"

    actions = [clone_dialog_scripts, archive_script, add_label, clear_label]
    action_form = DialogScriptLabelForm

@admin.register(DialogStateTransition)
class DialogStateTransitionAdmin(admin.ModelAdmin):
    list_display = ('dialog', 'when', 'state_id', 'prior_state_id')
    list_filter = ('when',)
