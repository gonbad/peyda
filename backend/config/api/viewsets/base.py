"""
Base ViewSet for all API endpoints.
"""
from rest_framework import viewsets, status
from rest_framework.response import Response
from typing import Type, TypeVar, Optional, Tuple, Dict, Any

from infrastructure.bootstrap import get_container

T = TypeVar('T')


class BaseViewSet(viewsets.ViewSet):
    """
    Base ViewSet with common functionality.
    
    Provides:
    - DI container access
    - Command/Query execution
    - Standard error responses
    """
    
    def get_container(self):
        """Get the DI container."""
        return get_container()
    
    def get_command(self, command_class: Type[T]) -> T:
        """Get a Command instance from the container."""
        return self.get_container().get(command_class)
    
    def get_query(self, query_class: Type[T]) -> T:
        """Get a Query instance from the container."""
        return self.get_container().get(query_class)
    
    def success(self, data: Dict[str, Any], status_code: int = 200) -> Response:
        """
        Create success response.
        
        Args:
            data: Response data dict
            status_code: HTTP status code (default 200)
        """
        return Response(data, status=status_code)
    
    def error(
        self, 
        message: str, 
        code: str, 
        status_code: int = 400,
        details: dict = None
    ) -> Response:
        """Create error response."""
        error_data = {
            'error': message,
            'code': code,
        }
        if details:
            error_data['details'] = details
        return Response(error_data, status=status_code)
    
    def not_found(self, message: str = "Not found") -> Response:
        """Create 404 response."""
        return self.error(message, "NOT_FOUND", status.HTTP_404_NOT_FOUND)
    
    def forbidden(self, message: str = "Forbidden") -> Response:
        """Create 403 response."""
        return self.error(message, "FORBIDDEN", status.HTTP_403_FORBIDDEN)
