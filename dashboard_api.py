from django.urls import reverse

def dashboard_pages():
    return [{
        'title': 'Dialog Scripts',
        'icon': 'speaker_notes',
        'url': reverse('dashboard_dialog_scripts'),
    }]
