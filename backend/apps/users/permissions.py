"""
Permissions for the users module

This module defines custom permission classes to control access
to user-related resources in the system. Permissions are used
in conjunction with Django REST Framework views to ensure that only
authorized users can perform certain operations.

Available permissions:
    - BasePermission: Base class from Django REST Framework for creating custom permissions
    - SAFE_METHODS: Constant that defines safe HTTP methods (GET, HEAD, OPTIONS)

When to use:
    - Import the necessary permission classes in views or viewsets
    - Use SAFE_METHODS to differentiate read operations from write operations
    - Extend BasePermission to create project-specific custom permissions
"""


from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrReadOnly(BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    
    This permission class grants read-only access to any request,
    but only allows write permissions to the owner of the object.
    
    Attributes:
        Inherits from BasePermission
        
    Methods:
        has_object_permission: Determines if the user has permission to access the object
    """

    def has_object_permission(self, request, view, obj):
        """
        Check if the user has permission to perform the requested action on the object.
        
        Args:
            request: The HTTP request being made
            view: The view that is being accessed
            obj: The object being accessed
            
        Returns:
            bool: True if the user has permission, False otherwise
            
        Logic:
            - Read permissions (GET, HEAD, OPTIONS) are allowed to any request
            - Write permissions are only allowed to the owner of the object
        """
        if request.method in SAFE_METHODS:
            return True
                
        elif request.method == 'DELETE':
            return request.user.is_staff  # Só admin pode deletar
        else:  # POST, PATCH
            return obj.user == request.user
    


    ### Para o futuro, trabalhar defensive programming e method specific logic