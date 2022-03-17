# pylint: disable=line-too-long, no-member
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

from builtins import str # pylint: disable=redefined-builtin

import importlib
import json
import sys
import traceback

import gettext

from six import python_2_unicode_compatible

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

try:
    from django.db.models import JSONField
except ImportError:
    from django.contrib.postgres.fields import JSONField

from django.db import models
from django.template import Template, Context
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils import timezone
from django.utils.html import mark_safe

from .dialog import DialogMachine, fetch_default_logger, ExternalChoiceNode, DialogError

FINISH_REASONS = (
    ('not_finished', 'Not Finished'),
    ('dialog_concluded', 'Dialog Concluded'),
    ('user_cancelled', 'User Cancelled'),
    ('dialog_cancelled', 'Dialog Cancelled'),
    ('dialog_error', 'Dialog Error'),
    ('timed_out', 'Timed Out'),
)

_ = gettext.gettext

def apply_template(obj, context_dict):
    if isinstance(obj, str):
        template = Template(obj)
        context = Context(context_dict)

        return template.render(context)

    if isinstance(obj, list):
        new_list = []

        for item in obj:
            new_list.append(apply_template(item, context_dict))

        return new_list

    if isinstance(obj, dict):
        new_dict = {}

        for key in obj:
            new_dict[key] = apply_template(obj[key], context_dict)

        return new_dict

    return obj

@python_2_unicode_compatible
class DialogScript(models.Model):
    name = models.CharField(max_length=1024, default='New Dialog Script')
    created = models.DateTimeField(auto_now_add=True, null=True)

    embeddable = models.BooleanField(default=False)

    identifier = models.SlugField(max_length=1024, null=True, blank=True)

    labels = models.TextField(max_length=(1024 * 1024), null=True, blank=True)

    definition = JSONField(null=True, blank=True)

    def is_valid(self):
        if isinstance(self.definition, list) is False:
            return False

        if self.definition:
            return True

        return False

    def definition_json(self):
        return mark_safe(json.dumps(self.definition))

    def __str__(self): # pylint: disable=invalid-str-returned
        return self.name

    def labels_list(self):
        if self.labels is None:
            return []

        cleaned_labels = []

        for line in self.labels.splitlines():
            tokens = line.split('|')

            cleaned_labels.append(tokens[-1])

        return cleaned_labels

    def priority_for_label(self, label):
        label_suffix = '|%s' % label

        for line in self.labels.splitlines():

            if line.endswith(label_suffix):
                return int(line.replace(label_suffix, ''))

        if hasattr(sys, 'maxint'):
            return sys.maxint

        return sys.maxsize

    def admin_labels(self):
        class Meta: # pylint: disable=too-few-public-methods, unused-variable, old-style-class, no-init
            verbose_name = _('Script labels')

        if self.labels is None:
            return None

        return '; '.join(self.labels_list())

    def get_absolute_url(self):
        try:
            return reverse('builder_dialog', args=[str(self.pk)])
        except NoReverseMatch:
            pass

        return '/admin/django_dialog_engine/dialogscript/' + str(self.pk) + '/change'

    def size(self):
        return len(self.definition)

    def last_started(self):
        last_dialog = self.dialogs.all().order_by('-started').first()

        if last_dialog is not None:
            return last_dialog.started

        return None

    def last_finished(self):
        last_dialog = self.dialogs.exclude(finished=None).order_by('-finished').first()

        if last_dialog is not None:
            return last_dialog.finished

        return None

    def dialog_machine(self):
        return DialogMachine(self.definition, {})

    def broadcast_changes(self, updates):
        for app in settings.INSTALLED_APPS:
            try:
                dialog_module = importlib.import_module('.dialog_api', package=app)

                dialog_module.dialog_updated(self, timezone.now(), updates)
            except ImportError:
                pass
            except AttributeError:
                pass

    def save(self, *args, **kwargs): # pylint: disable=arguments-differ, signature-differs
        if self.pk:
            cls = self.__class__
            old = cls.objects.get(pk=self.pk)

            new = self

            changed_fields = {}

            for field in cls._meta.get_fields(): # pylint: disable=protected-access
                field_name = field.name

                try:
                    if getattr(old, field_name) != getattr(new, field_name):
                        changed_fields[field_name] = {
                            'original': getattr(old, field_name),
                            'updated': getattr(new, field_name)
                        }

                except Exception as ex: # nosec # pylint: disable=broad-except, unused-variable
                    pass # Catch field does not exist exception

            self.broadcast_changes(changed_fields)

        super(DialogScript, self).save(*args, **kwargs) # pylint: disable=super-with-arguments

@python_2_unicode_compatible
class Dialog(models.Model):
    key = models.CharField(null=True, blank=True, max_length=128)

    script = models.ForeignKey(DialogScript, related_name='dialogs', null=True, blank=True, on_delete=models.SET_NULL)
    dialog_snapshot = JSONField(null=True, blank=True)

    started = models.DateTimeField()
    finished = models.DateTimeField(null=True, blank=True)

    finish_reason = models.CharField(max_length=128, choices=FINISH_REASONS, default='not_finished')

    metadata = JSONField(default=dict)

    def __str__(self):
        if self.script is not None:
            return self.script.name

        return 'dialog-' + str(self.pk)

    def is_valid(self):
        if self.script is None:
            return False

        if self.script.is_valid() is False:
            return False

        return True

    def finish(self, finish_reason='dialog_concluded'):
        self.finished = timezone.now()
        self.finish_reason = finish_reason

        self.save()

        for app in settings.INSTALLED_APPS:
            try:
                dialog_module = importlib.import_module('.dialog_api', package=app)

                dialog_module.finished_dialog(self)
            except ImportError:
                pass
            except AttributeError:
                pass

    def is_active(self):
        return self.finished is None

    def process(self, response=None, extras=None):
        if extras is None:
            extras = {}

        actions = []

        if self.finished is not None:
            return actions

        if self.dialog_snapshot is None:
            self.dialog_snapshot = self.script.definition
            self.save()

        last_transition = self.transitions.order_by('-when').first()

        try:
            dialog_machine = DialogMachine(self.dialog_snapshot, self.metadata, django_object=self)

            if last_transition is not None:
                dialog_machine.advance_to(last_transition.state_id)

            logger = fetch_default_logger()

            try:
                logger = settings.FETCH_LOGGER()
            except AttributeError:
                pass

            transition = dialog_machine.evaluate(response=response, last_transition=last_transition, extras=extras, logger=logger)

            if transition is None:
                pass # Nothing to do
            elif last_transition is None or last_transition.state_id != transition.new_state_id or transition.refresh is True:
                new_actions = []

                if transition.new_state_id is None:
                    self.finished = timezone.now()
                    self.finish_reason = 'dialog_concluded'
                    self.metadata['last_transition_details'] = transition.metadata

                    self.save()
                else:
                    new_transition = DialogStateTransition(dialog=self)
                    new_transition.when = timezone.now()
                    new_transition.state_id = transition.new_state_id
                    new_transition.metadata = transition.metadata

                    if last_transition is not None:
                        new_transition.prior_state_id = last_transition.state_id

                    new_transition.save()

                    new_actions = new_transition.actions()

                    if new_actions is None:
                        new_actions = []

                new_actions = apply_template(new_actions, self.metadata)

                actions.extend(new_actions)

            return actions
        except DialogError:
            print('Encountered an issue in dialog %d:' % self.pk)
            traceback.print_exc()
            print('Force-finishing %d.' % self.pk)

            self.metadata['dialog_error'] = traceback.format_exc()

            self.finish('dialog_error')

            return []

    def advance_to(self, state_id):
        last_transition = self.transitions.order_by('-when').first()

        new_transition = DialogStateTransition(dialog=self)
        new_transition.when = timezone.now()
        new_transition.state_id = state_id

        if last_transition is not None:
            new_transition.prior_state_id = last_transition.state_id
            new_transition.metadata = last_transition.metadata

        new_transition.save()

        dialog_machine = DialogMachine(self.dialog_snapshot, self.metadata)

        dialog_machine.advance_to(new_transition.state_id)

        actions = dialog_machine.current_node.actions()

        if actions is None:
            actions = []

        new_actions = new_transition.actions()

        if new_actions is not None:
            actions.extend(new_actions)

        return actions

    def current_state_id(self):
        last_transition = self.transitions.order_by('-when').first()

        if last_transition is not None:
            return last_transition.state_id

        return None

    def available_actions(self):
        actions = []

        last_transition = self.transitions.order_by('-when').first()

        dialog_machine = DialogMachine(self.dialog_snapshot, self.metadata)

        if last_transition is not None:
            dialog_machine.advance_to(last_transition.state_id)

            if isinstance(dialog_machine.current_node, ExternalChoiceNode):
                dialog_actions = dialog_machine.current_node.actions()

                for action in dialog_actions:
                    actions.extend(action['choices'])

        return actions

    def prior_transitions(self, new_state_id, prior_state_id, reason=None):
        transitions = []

        for transition in self.transitions.filter(state_id=new_state_id, prior_state_id=prior_state_id):
            if reason is None or transition.metadata['reason'] == reason:
                transitions.append(transition)

        return transitions

    def get_value(self, key):
        if 'values' in self.metadata:
            if key in self.metadata['values']:
                return self.metadata['values'][key]

        return None

    def put_value(self, key, value):
        if ('values' in self.metadata) is False:
            self.metadata['values'] = {}

        if value is None and key in self.metadata['values']:
            del self.metadata['values'][key]
        else:
            self.metadata['values'][key] = value

        self.save()

    def pop_value(self, key):
        value = self.get_value(key)

        if value is None: # pylint: disable=no-else-return
            return None
        elif isinstance(value, (list,)):
            if len(value) > 0: # pylint: disable=len-as-condition
                new_value = value.pop()

                self.put_value(key, value)

                return new_value

            return None
        else:
            del self.metadata['values'][key]
            self.save()

        return value

    def push_value(self, key, value):
        list_value = self.get_value(key)

        if list_value is None:
            list_value = []
        elif isinstance(list_value, (list,)) is False:
            list_value = [list_value]

        if isinstance(value, (list,)):
            list_value.extend(value)
        else:
            list_value.append(value)

        self.put_value(key, list_value)

@receiver(post_save, sender=Dialog)
def initialize_dialog(sender, instance, created, **kwargs): # pylint: disable=unused-argument, too-many-locals, too-many-branches
    while created is True:
        for app in settings.INSTALLED_APPS:
            try:
                dialog_module = importlib.import_module('.dialog_api', package=app)

                dialog_module.initialize_dialog(instance)
            except ImportError:
                pass
            except AttributeError:
                pass

        replacements = []

        machine = DialogMachine(instance.dialog_snapshot)

        for node in machine.nodes():
            replacement_nodes = node.replacement_definitions(instance.dialog_snapshot)

            if replacement_nodes is not None:
                replacements.append((node, replacement_nodes,))

        if len(replacements) == 0: # pylint: disable=len-as-condition
            break

        for replacement in replacements:
            original_node = replacement[0] # embed node
            replacement_nodes = replacement[1] # new nodes

            outer_begin = original_node.node_id # entry point
            outer_end = original_node.next_node_id # exit point

            inner_begin = outer_end # entry point
            inner_end = outer_end # exit point

            replacement_to_remove = []

            for node_def in replacement_nodes:
                if node_def['type'] == 'begin':
                    inner_begin = node_def['next_id']

                    replacement_to_remove.append(node_def)
                elif node_def['type'] == 'end':
                    inner_end = node_def['id']

                    replacement_to_remove.append(node_def)

            for node_def in replacement_to_remove:
                while node_def in replacement_nodes:
                    replacement_nodes.remove(node_def)

            instance.dialog_snapshot.extend(replacement_nodes)

            entry_pause = {
                'type': 'pause',
                'id': outer_begin,
                'next_id':  inner_begin,
                'duration': 0,
                'comment': 'Automatically inserted to support embedded dialog (%s / enter).' % outer_begin
            }

            instance.dialog_snapshot.append(entry_pause)

            exit_pause = {
                'type': 'pause',
                'id': inner_end,
                'next_id':  outer_end,
                'duration': 0,
                'comment': 'Automatically inserted to support embedded dialog (%s / exit).' % outer_begin
            }

            instance.dialog_snapshot.append(exit_pause)

            instance.save()


@python_2_unicode_compatible
class DialogStateTransition(models.Model):
    dialog = models.ForeignKey(Dialog, related_name='transitions', null=True, on_delete=models.SET_NULL)

    when = models.DateTimeField()
    state_id = models.CharField(max_length=128)
    prior_state_id = models.CharField(max_length=128, null=True, blank=True)

    metadata = JSONField(default=dict)

    def __str__(self):
        return str(self.prior_state_id) + ' -> ' + str(self.state_id)

    def actions(self):
        if 'actions' in self.metadata:
            return self.metadata['actions']

        return []
