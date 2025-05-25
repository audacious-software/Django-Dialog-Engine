# pylint: disable=no-member,line-too-long,ungrouped-imports
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from prettyjson import PrettyJSONWidget

from django import forms

from django.contrib import admin

from django.contrib.admin.helpers import ActionForm
from django.db.models import Q

try:
    from django.db.models import JSONField
except ImportError:
    from django.contrib.postgres.fields import JSONField

try:
    from docker_utils.admin import PortableModelAdmin as ModelAdmin
except ImportError:
    from django.contrib.admin import ModelAdmin as ModelAdmin # pylint: disable=useless-import-alias

from .models import Dialog, DialogScript, DialogScriptVersion, DialogStateTransition

@admin.register(Dialog)
class DialogAdmin(ModelAdmin):
    list_display = ('key', 'script', 'current_state_id', 'started', 'finished', 'finish_reason',)
    search_fields = ('key', 'dialog_snapshot', 'finish_reason', 'script__name',)
    list_filter = ('started', 'finished', 'finish_reason')

    formfield_overrides = {
        JSONField: {'widget': PrettyJSONWidget(attrs={'initial': 'parsed'})}
    }

    def export_objects(self, request, queryset):
        return self.portable_model_export_items(request, queryset)

    export_objects.short_description = 'Export selected dialogs'

    actions = [
        'export_objects',
    ]

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

        query = query | Q(labels__contains=('|%s' % self.value())) # pylint: disable=superfluous-parens

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

@admin.register(DialogScriptVersion)
class DialogScriptVersionAdmin(admin.ModelAdmin):
    list_display = ('dialog_script', 'name', 'identifier', 'updated')
    list_filter = ('updated', 'created', 'dialog_script', 'identifier')
    search_fields = ('name', 'identifier', 'definition', 'labels',)

    formfield_overrides = {
        JSONField: {'widget': PrettyJSONWidget(attrs={'initial': 'parsed'})}
    }

    def restore_dialog_script_version(self, request, queryset): # pylint: disable=unused-argument
        for item in queryset:
            item.restore_version()

    restore_dialog_script_version.short_description = "Restore selected versions"

    actions = [restore_dialog_script_version]

class DialogScriptVersionInline(admin.TabularInline):
    model = DialogScriptVersion

    verbose_name = 'Version'
    verbose_name_plural = 'Versions'
    template = 'admin_inlines/versions_tabular.html'

    fields = ['updated', 'creator', 'size']
    readonly_fields = ['updated', 'creator', 'size']
    ordering = ('-updated',)

    def has_add_permission(self, request, obj=None): # pylint: disable=arguments-differ,unused-argument
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(DialogScript)
class DialogScriptAdmin(ModelAdmin):
    list_display = ('name', 'identifier', 'size', 'created', 'admin_labels',)
    search_fields = ('name', 'identifier', 'definition', 'labels',)
    list_filter = (DialogScriptArchiveFilter, 'created', 'embeddable', DialogScriptLabelFilter,)

    formfield_overrides = {
        JSONField: {'widget': PrettyJSONWidget(attrs={'initial': 'parsed'})}
    }

    inlines = [
        DialogScriptVersionInline,
    ]

    def clone_dialog_scripts(self, request, queryset): # pylint: disable=unused-argument,no-self-use
        for item in queryset:
            item.pk = None
            item.name = item.name + ' (Copy)'
            item.identifier = item.identifier + '-copy'
            item.save()

    clone_dialog_scripts.short_description = 'Clone selected dialog scripts'

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

    add_label.short_description = 'Add label to selected dialog scripts'

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

    clear_label.short_description = 'Clear label from selected dialog scripts'

    def archive_script(self, request, queryset):
        count = 0

        for script in queryset:
            if script.add_label('archived'):
                count += 1

        self.message_user(request, '%d dialog script(s) archived.' % count)

    archive_script.short_description = 'Archive selected dialog scripts'

    def make_embeddable(self, request, queryset):
        count = queryset.update(embeddable=True)

        self.message_user(request, '%d dialog script(s) marked embeddable.' % count)

    make_embeddable.short_description = 'Make selected dialog scripts embeddable'

    def remove_embeddable(self, request, queryset):
        count = queryset.update(embeddable=True)

        self.message_user(request, '%d dialog script(s) are no longer embeddable.' % count)

    remove_embeddable.short_description = 'Make selected dialog scripts unembeddable'

    def export_objects(self, request, queryset):
        return self.portable_model_export_items(request, queryset)

    export_objects.short_description = 'Export selected dialog scripts'

    actions = [
        'export_objects',
        'clone_dialog_scripts',
        'archive_script',
        'add_label',
        'clear_label',
        'make_embeddable',
        'remove_embeddable'
    ]

    action_form = DialogScriptLabelForm

@admin.register(DialogStateTransition)
class DialogStateTransitionAdmin(admin.ModelAdmin):
    list_display = ('dialog', 'when', 'state_id', 'prior_state_id')
    list_filter = ('when',)

    formfield_overrides = {
        JSONField: {'widget': PrettyJSONWidget(attrs={'initial': 'parsed'})}
    }
