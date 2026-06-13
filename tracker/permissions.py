"""
permissions.py — Role-Based Access Control
==========================================
Roles:
  admin      – full CRUD, sees all data
  beekeeper  – CRUD on own farms/hives/harvests
  farm_user  – can only POST new harvests (own farm's hives only)
  viewer     – read-only, no writes
"""
from rest_framework.response import Response
from rest_framework import status

ROLE_ADMIN      = 'admin'
ROLE_BEEKEEPER  = 'beekeeper'
ROLE_FARM_USER  = 'farm_user'
ROLE_VIEWER     = 'viewer'

ROLE_PERMISSIONS = {
    ROLE_ADMIN:     {'can_read': True,  'can_write': True,  'can_delete': True,  'harvest_only': False},
    ROLE_BEEKEEPER: {'can_read': True,  'can_write': True,  'can_delete': True,  'harvest_only': False},
    ROLE_FARM_USER: {'can_read': True,  'can_write': True,  'can_delete': False, 'harvest_only': True},
    ROLE_VIEWER:    {'can_read': True,  'can_write': False, 'can_delete': False, 'harvest_only': False},
}


def get_session_role(request):
    return request.session.get('role', ROLE_VIEWER)


def get_session_beekeeper_id(request):
    return request.session.get('beekeeper_id')


def has_permission(request, action):
    role  = get_session_role(request)
    perms = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS[ROLE_VIEWER])
    return perms.get(f'can_{action}', False)


def is_harvest_only(request):
    role  = get_session_role(request)
    perms = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS[ROLE_VIEWER])
    return perms.get('harvest_only', False)


class RBACMixin:
    """
    Applied to all ModelViewSets.
    - farm_user: can only write to HarvestViewSet; all other write actions → 403
    - viewer: all writes → 403
    - beekeeper: scoped to own data
    - admin: unrestricted
    """

    def get_queryset(self):
        qs    = super().get_queryset()
        role  = get_session_role(self.request)
        bk_id = get_session_beekeeper_id(self.request)

        if role in (ROLE_BEEKEEPER, ROLE_FARM_USER) and bk_id:
            model_name = qs.model.__name__
            if model_name == 'Beekeeper':
                qs = qs.filter(id=bk_id)
            elif model_name == 'Farm':
                qs = qs.filter(beekeeper_id=bk_id)
            elif model_name == 'Hive':
                qs = qs.filter(farm__beekeeper_id=bk_id)
            elif model_name == 'Harvest':
                qs = qs.filter(hive__farm__beekeeper_id=bk_id)
        return qs

    def _check_write_permission(self, request):
        model_name = self.queryset.model.__name__
        role = get_session_role(request)

        # farm_user can only write harvests
        if role == ROLE_FARM_USER and model_name != 'Harvest':
            return Response(
                {'error': 'Farm users can only add harvest records.',
                 'your_role': role},
                status=status.HTTP_403_FORBIDDEN
            )

        if request.method in ('POST', 'PUT', 'PATCH'):
            if not has_permission(request, 'write'):
                return Response(
                    {'error': 'Permission denied.', 'your_role': role},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif request.method == 'DELETE':
            if not has_permission(request, 'delete'):
                return Response(
                    {'error': 'Permission denied.', 'your_role': role},
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
