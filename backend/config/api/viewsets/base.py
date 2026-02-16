"""
Base ViewSet for all API endpoints.
"""
from rest_framework import viewsets, status
from rest_framework.response import Response
from pydantic import ValidationError
from typing import Type, TypeVar, Optional, Tuple

from infrastructure.bootstrap import get_container
from config.api.contracts.base import ErrorResponse

T = TypeVar('T')


class BaseViewSet(viewsets.ViewSet):
    """
    Base ViewSet with common functionality.
    
    Provides:
    - DI container access
    - Command/Query execution
    - Pydantic validation
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
    
    def validate_request(
        self, 
        request_model: Type[T], 
        data: dict
    ) -> Tuple[Optional[T], Optional[Response]]:
        """
        Validate request data with Pydantic model.
        
        Returns:
            Tuple of (validated_model, None) on success
            Tuple of (None, error_response) on failure
        """
        try:
            return request_model(**data), None
        except ValidationError as e:
            return None, self.validation_error(e)
    
    def validation_error(self, error: ValidationError) -> Response:
        """Create validation error response."""
        return Response(
            ErrorResponse(
                error="Validation Error",
                code="VALIDATION_ERROR",
                details={'errors': error.errors()}
            ).model_dump(),
            status=status.HTTP_400_BAD_REQUEST
        )
    
    def success(self, data, response_model=None) -> Response:
        """
        Create success response.
        
        Args:
            data: Response data (dict or object)
            response_model: Optional Pydantic model to validate response
        """
        if response_model:
            if hasattr(data, '__dict__') and not isinstance(data, dict):
                validated = response_model.model_validate(data)
            else:
                validated = response_model(**data)
            return Response(validated.model_dump())
        return Response(data)
    
    def error(
        self, 
        message: str, 
        code: str, 
        status_code: int = 400,
        details: dict = None
    ) -> Response:
        """Create error response."""
        return Response(
            ErrorResponse(
                error=message, 
                code=code,
                details=details
            ).model_dump(),
            status=status_code
        )
    
    def not_found(self, message: str = "Not found") -> Response:
        """Create 404 response."""
        return self.error(message, "NOT_FOUND", status.HTTP_404_NOT_FOUND)
    
    def forbidden(self, message: str = "Forbidden") -> Response:
        """Create 403 response."""
        return self.error(message, "FORBIDDEN", status.HTTP_403_FORBIDDEN)
