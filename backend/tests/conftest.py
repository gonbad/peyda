"""
Pytest configuration and fixtures for Peyda tests.
"""
import os
import pytest
from django.test import Client

# Use fakes for testing
os.environ.setdefault('USE_FAKES', 'true')


@pytest.fixture(autouse=True)
def reset_container():
    """Reset DI container before each test."""
    from infrastructure.bootstrap import Container
    Container.reset()
    yield
    Container.reset()


@pytest.fixture
def api_client():
    """Django test client for API requests."""
    return Client()


@pytest.fixture
def user(db):
    """Create a test user."""
    from apps.users.models import User
    return User.objects.create(
        phone='+989123456789',
        role=User.Role.USER,
    )


@pytest.fixture
def mawkab_owner(db):
    """Create a test mawkab owner."""
    from apps.users.models import User
    from apps.mawkab.models import Mawkab
    
    mawkab = Mawkab.objects.create(
        name='موکب تست',
        owner_name='صاحب موکب تست',
        owner_phone='+989123456788',
        latitude=34.6416,
        longitude=50.8746,
        status=Mawkab.Status.APPROVED,
    )
    
    user = User.objects.create(
        phone='+989123456788',
        role=User.Role.MAWKAB_OWNER,
        mawkab_id=mawkab.id,
    )
    
    return user


@pytest.fixture
def auth_token(user):
    """Generate JWT token for test user."""
    import jwt
    from datetime import datetime, timedelta
    from django.conf import settings
    
    payload = {
        'user_id': user.id,
        'phone': user.phone,
        'exp': datetime.utcnow() + timedelta(days=30),
        'iat': datetime.utcnow(),
    }
    
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


@pytest.fixture
def auth_headers(auth_token):
    """Authorization headers for authenticated requests."""
    return {'HTTP_AUTHORIZATION': f'Bearer {auth_token}'}
