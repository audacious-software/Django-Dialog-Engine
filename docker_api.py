# pylint: disable=line-too-long, no-member

import json

import iso8601

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core import serializers

from .models import DialogScript, DialogScriptVersion, Dialog, DialogStateTransition

def import_objects(file_type, import_file):
    if file_type == 'django_dialog_engine.dialogscript':
        return import_dialog_scripts(import_file)

    if file_type == 'django_dialog_engine.dialog':
        return import_dialogs(import_file)

    return None

def import_dialogs(import_file): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    user_messages = []

    with import_file.open() as file_stream:
        dialogs_json = json.load(file_stream)

        dialogs_imported = 0
        transitions_imported = 0

        for dialog_json in dialogs_json: # pylint: disable=too-many-nested-blocks
            if dialog_json.get('model', None) == 'django_dialog_engine.dialog':
                dialog_obj = Dialog()

                for field_key in dialog_json.get('fields', {}).keys():
                    field_value = dialog_json.get('fields', {}).get(field_key, None)

                    if field_key in ('started', 'finished'):
                        if field_value is not None:
                            field_value = iso8601.parse_date(field_value)
                    elif field_key == 'script':
                        field_value = DialogScript.objects.filter(identifier=field_value).first()

                    setattr(dialog_obj, field_key, field_value)

                dialog_obj.save()

                dialogs_imported += 1

                for transition in dialog_json.get('transitions', []):
                    if transition.get('model', None) == 'django_dialog_engine.dialogstatetransition':
                        transition_obj = DialogStateTransition(dialog=dialog_obj)

                        for field_key in transition.get('fields', {}).keys():
                            field_value = transition.get('fields', {}).get(field_key, None)

                            if field_key == 'when':
                                if field_value is not None:
                                    field_value = iso8601.parse_date(field_value)

                            setattr(transition_obj, field_key, field_value)

                        transition_obj.save()

                        transitions_imported += 1

        if dialogs_imported > 1:
            user_messages.append(('%s dialogs imported.' % dialogs_imported, messages.SUCCESS))
        elif dialogs_imported == 1:
            user_messages.append(('1 dialog imported.', messages.SUCCESS))
        else:
            user_messages.append(('No dialogs imported.', messages.INFO))

        if transitions_imported > 1:
            user_messages.append(('%s dialog state transitions imported.' % transitions_imported, messages.SUCCESS))
        elif transitions_imported == 1:
            user_messages.append(('1 dialog state transition imported.', messages.SUCCESS))
        else:
            user_messages.append(('No dialog state transitions imported.', messages.INFO))

    return user_messages

def import_dialog_scripts(import_file): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    user_messages = []

    with import_file.open() as file_stream:
        scripts_json = json.load(file_stream)

        scripts_updated = 0
        scripts_created = 0
        versions_imported = 0

        for script_json in scripts_json: # pylint: disable=too-many-nested-blocks
            if script_json.get('model', None) == 'django_dialog_engine.dialogscript':
                identifier = script_json.get('fields', {}).get('identifier', None)

                if identifier is not None:
                    script_obj = DialogScript.objects.filter(identifier=identifier).first()

                    if script_obj is None:
                        script_obj = DialogScript.objects.create(identifier=identifier)
                        script_obj.versions.all().delete()

                        scripts_created += 1
                    else:
                        scripts_updated += 1

                    for field_key in script_json.get('fields', {}).keys():
                        field_value = script_json.get('fields', {}).get(field_key, None)

                        if field_key in ('created', 'updated'):
                            if field_value is not None:
                                field_value = iso8601.parse_date(field_value)

                        setattr(script_obj, field_key, field_value)

                    script_obj.save()

                    script_obj.versions.all().order_by('-pk').first().delete()

                    DialogScriptVersion.objects.filter(dialog_script=None).delete()

                    for version in script_json.get('versions', []):
                        if version.get('model', None) == 'django_dialog_engine.dialogscriptversion':
                            updated_str = version.get('fields', {}).get('updated', None)

                            updated = iso8601.parse_date(updated_str)

                            version_obj = DialogScriptVersion.objects.filter(dialog_script=script_obj, updated=updated).first()

                            if version_obj is None:
                                version_obj = DialogScriptVersion.objects.create(dialog_script=script_obj, updated=updated)

                            for field_key in version.get('fields', {}).keys():
                                field_value = version.get('fields', {}).get(field_key, None)

                                if field_key in ('created', 'updated'):
                                    if field_value is not None:
                                        field_value = iso8601.parse_date(field_value)
                                elif field_key == 'creator__username':
                                    creator = get_user_model().objects.filter(username=field_value).first()

                                    if creator is None:
                                        creator = get_user_model().objects.create(username=field_value, is_active=False)

                                    field_key = 'creator'
                                    field_value = creator

                                setattr(version_obj, field_key, field_value)

                            version_obj.save()

                            versions_imported += 1

        if scripts_updated > 1:
            user_messages.append(('%s dialog scripts updated.' % scripts_updated, messages.SUCCESS))
        elif scripts_updated == 1:
            user_messages.append(('1 dialog script updated.', messages.SUCCESS))

        if scripts_created > 1:
            user_messages.append(('%s dialog scripts created.' % scripts_created, messages.SUCCESS))
        elif scripts_created == 1:
            user_messages.append(('1 dialog script created.', messages.SUCCESS))

        if scripts_updated == 0 and scripts_created == 0:
            user_messages.append(('No dialog scripts imported.', messages.INFO))

    return user_messages

def export_dialog_scripts(queryset):
    to_export = []

    for script in queryset:
        script_json = json.loads(serializers.serialize('json', DialogScript.objects.filter(pk=script.pk)))[0]

        del script_json['pk']

        script_json['versions'] = []

        for version in script.versions.all().order_by('created'):
            version_json = json.loads(serializers.serialize('json', DialogScriptVersion.objects.filter(pk=version.pk)))[0]

            del version_json['pk']
            del version_json['fields']['dialog_script']

            creator = get_user_model().objects.filter(pk=version_json['fields']['creator']).first()

            if creator is None:
                version_json['fields']['creator__username'] = 'unknown-dialog-script-creator'
            else:
                version_json['fields']['creator__username'] = creator.username

            del version_json['fields']['creator']

            script_json['versions'].append(version_json)

        to_export.append(script_json)

    return to_export

def export_dialogs(queryset):
    to_export = []

    for dialog in queryset:
        dialog_json = json.loads(serializers.serialize('json', Dialog.objects.filter(pk=dialog.pk)))[0]

        del dialog_json['pk']

        if dialog.script is not None:
            dialog_json['fields']['script'] = dialog.script.identifier

        dialog_json['transitions'] = []

        for transition in dialog.transitions.all().order_by('when'):
            transition_json = json.loads(serializers.serialize('json', DialogStateTransition.objects.filter(pk=transition.pk)))[0]

            del transition_json['pk']
            del transition_json['fields']['dialog']

            dialog_json['transitions'].append(transition_json)

        to_export.append(dialog_json)

    return to_export

def export_objects(queryset, queryset_name):
    to_export = []

    if queryset_name == 'DialogScript':
        to_export.extend(export_dialog_scripts(queryset))
    elif queryset_name == 'Dialog':
        to_export.extend(export_dialogs(queryset))

    return to_export
