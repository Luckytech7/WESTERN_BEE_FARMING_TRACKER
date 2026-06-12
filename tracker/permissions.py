"""
permissions.py — Role-Based Access Control
==========================================
Roles:
  admin      – full CRUD on everything, sees all data
  beekeeper  – CRUD on own farms/hives/harvests only
  viewer     – read-only

Role stored in Django session after login.
"""
from rest_framework.response import Response
from rest_framework import status


ROLE_ADMIN      = 'admin'
ROLE_BEEKEEPER  = 'beekeeper'
ROLE_VIEWER     = 'viewer'

ROLE_PERMISSIONS = {
    ROLE_ADMIN:     {'can_read': True,  'can_write': True,  'can_delete': True},
    ROLE_BEEKEEPER: {'can_read': True,  'can_write': True,  'can_delete': True},
    ROLE_VIEWER:    {'can_read': True,  'can_write': False, 'can_delete': False},
}


def get_session_role(request):
    return request.session.get('role', ROLE_VIEWER)


def get_session_beekeeper_id(request):
    return request.session.get('beekeeper_id')


def has_permission(request, action):
    role  = get_session_role(request)
    perms = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS[ROLE_VIEWER])
    return perms.get(f'can_{action}', False)


class RBACMixin:
    """
    Mixin for ModelViewSet.
    - Viewer role: GET allowed, POST/PUT/PATCH/DELETE → 403
    - Beekeeper role: queryset scoped to own data
    - Admin role: unrestricted
    """

    def get_queryset(self):
        qs = super().get_queryset()
        role        = get_session_role(self.request)
        bk_id       = get_session_beekeeper_id(self.request)

        if role == ROLE_BEEKEEPER and bk_id:
            model_name = qs.model.__name__
            if model_name == 'Farm':
                qs = qs.filter(beekeeper_id=bk_id)
            elif model_name == 'Hive':
                qs = qs.filter(farm__beekeeper_id=bk_id)
            elif model_name == 'Harvest':
                qs = qs.filter(hive__farm__beekeeper_id=bk_id)
        return qs

    def _check_write_permission(self, request):
        """Return None (allowed) or a Response (denied)."""
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            action = 'delete' if request.method == 'DELETE' else 'write'
            if not has_permission(request, action):
                return Response(
                    {'error': 'Permission denied.',
                     'your_role': get_session_role(request),
                     'required': action},
                    status=status.HTTP_403_FORBIDDEN
                )
        return None

    def create(self, request, *args, **kwargs):
        denied = self._check_write_permission(request)
        if denied: return denied
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        denied = self._check_write_permission(request)
        if denied: return denied
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        denied = self._check_write_permission(request)
        if denied: return denied
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        denied = self._check_write_permission(request)
        if denied: return denied
        return super().destroy(request, *args, **kwargs)
