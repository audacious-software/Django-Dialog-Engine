# pylint: disable=line-too-long, no-member
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from builtins import str # pylint: disable=redefined-builtin

import json

from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.html import mark_safe


from .dialog import DialogMachine, fetch_default_logger

FINISH_REASONS = (
    ('not_finished', 'Not Finished'),
    ('dialog_concluded', 'Dialog Concluded'),
    ('user_cancelled', 'User Cancelled'),
    ('dialog_cancelled', 'Dialog Cancelled'),
    ('timed_out', 'Timed Out'),
)

@python_2_unicode_compatible
class DialogScript(models.Model):
    name = models.CharField(max_length=1024, default='New Dialog Script')
    created = models.DateTimeField(auto_now_add=True, null=True)

    definition = JSONField(null=True, blank=True)

    def is_valid(self):
        if isinstance(self.definition, list) is False:
            return False

        if self.definition:
            return True

        return False

    def definition_json(self):
        return mark_safe(json.dumps(self.definition))

    def __str__(self):
        return str(self.name)


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
            return str(self.script)

        return 'dialog-' + str(self.pk)

    def is_valid(self):
        if self.script is None:
            return False

        if self.script.is_valid() is False:
            return False

        return True

    def is_active(self):
        return self.finished is None

    def process(self, response=None, extras=None):
        if extras is None:
            extras = {}

        if self.finished is not None:
            return []

        if self.dialog_snapshot is None:
            self.dialog_snapshot = self.script.definition
            self.save()

        last_transition = self.transitions.order_by('-when').first()

        dialog_machine = DialogMachine(self.dialog_snapshot, self.metadata)

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
            actions = []

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

                actions = new_transition.actions()

            return actions

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

        return new_transition.actions()


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
