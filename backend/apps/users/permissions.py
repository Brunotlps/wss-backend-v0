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
            - DELETE operations restricted to staff users only
            
        Notes:
            - For User objects: checks if obj == request.user
            - For related objects (Profile, Enrollment): checks if obj.user == request.user
            - For Course objects: checks if obj.instructor == request.user
        """
        if request.method in SAFE_METHODS:
            return True
                
        elif request.method == 'DELETE':
            return request.user.is_staff
        
        else:  # POST, PUT, PATCH
            # Handle User objects (obj is the user itself)
            if hasattr(obj, 'username') and hasattr(obj, 'email'):
                return obj == request.user
            
            # Handle objects with 'user' attribute (Profile, Enrollment, etc.)
            elif hasattr(obj, 'user'):
                return obj.user == request.user
            
            # Handle Course objects (instructor ownership)
            elif hasattr(obj, 'instructor'):
                return obj.instructor == request.user
            
            # Deny by default for unknown object types
            return False
    


    ### Para o futuro, trabalhar defensive programming e method specific logic