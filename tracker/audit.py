"""
Thin helper for writing AuditLog entries from anywhere in the codebase.
Import log_action and call it — it never raises.
"""


def _get_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR', '') or None


def log_action(request, action, *, resource='', resource_id='', detail=''):
    try:
        from .models import AuditLog
        AuditLog.objects.create(
            actor_name  = request.session.get('beekeeper_name', ''),
            actor_role  = request.session.get('role', ''),
            action      = action,
            resource    = resource,
            resource_id = str(resource_id) if resource_id else '',
            detail      = detail,
            ip_address  = _get_ip(request),
        )
    except Exception:
        pass  # audit must never break the main flow
