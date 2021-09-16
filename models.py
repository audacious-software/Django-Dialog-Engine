# pylint: disable=line-too-long, no-member
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from builtins import str # pylint: disable=redefined-builtin

import json

from six import python_2_unicode_compatible

from django.conf import settings

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

from .dialog import DialogMachine, fetch_default_logger, ExternalChoice

FINISH_REASONS = (
    ('not_finished', 'Not Finished'),
    ('dialog_concluded', 'Dialog Concluded'),
    ('user_cancelled', 'User Cancelled'),
    ('dialog_cancelled', 'Dialog Cancelled'),
    ('timed_out', 'Timed Out'),
)

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

    identifier = models.SlugField(max_length=1024, null=True, blank=True)

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

            if isinstance(dialog_machine.current_node, ExternalChoice):
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
