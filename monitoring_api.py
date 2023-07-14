# pylint: disable=no-member, line-too-long

from .models import DialogScript

def issues():
    error_count = 0

    for script in DialogScript.objects.all():
        if script.is_active():
            error_count += len(script.issues())
    detected_issues = []

    if error_count > 0:
        detected_issues.append(('Unhandled errors in active dialogs: %d. (Run "validate_dialog_scripts" command for details.)' % error_count))

    return detected_issues
