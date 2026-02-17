"""
Tests for OTP authentication flow.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestSendOTP:
    """Tests for POST /auth/send-otp"""
    
    def test_send_otp_success(self, api_client):
        """Should send OTP and return request_id."""
        response = api_client.post(
            '/api/v1/auth/send-otp',
            data={'phone': '+989123456789', 'country_code': '+98'},
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'request_id' in data
        assert 'expires_in' in data
    
    def test_send_otp_missing_phone(self, api_client):
        """Should return error if phone is missing."""
        response = api_client.post(
            '/api/v1/auth/send-otp',
            data={},
            content_type='application/json'
        )
        
        assert response.status_code == 400


@pytest.mark.django_db
class TestVerifyOTP:
    """Tests for POST /auth/verify-otp"""
    
    def test_verify_otp_invalid_request_id(self, api_client):
        """Should return error for invalid request_id."""
        response = api_client.post(
            '/api/v1/auth/verify-otp',
            data={'request_id': 'invalid', 'otp': '123456'},
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_verify_otp_missing_data(self, api_client):
        """Should return error if data is missing."""
        response = api_client.post(
            '/api/v1/auth/verify-otp',
            data={},
            content_type='application/json'
        )
        
        assert response.status_code == 400
