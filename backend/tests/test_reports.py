"""
Tests for reports endpoints.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestReportsList:
    """Tests for GET /reports"""
    
    def test_list_reports_unauthenticated(self, api_client):
        """Should return 401 for unauthenticated requests."""
        response = api_client.get('/api/v1/reports/')
        assert response.status_code == 401
    
    def test_list_reports_authenticated(self, api_client, user, auth_headers):
        """Should return reports list for authenticated user."""
        response = api_client.get('/api/v1/reports/', **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert 'reports' in data
        assert 'pagination' in data


@pytest.mark.django_db
class TestCreateReport:
    """Tests for POST /reports"""
    
    def test_create_report_unauthenticated(self, api_client):
        """Should return 401 for unauthenticated requests."""
        response = api_client.post(
            '/api/v1/reports/',
            data={},
            content_type='application/json'
        )
        assert response.status_code == 401
    
    def test_create_report_missing_data(self, api_client, user, auth_headers):
        """Should return error for missing required fields."""
        response = api_client.post(
            '/api/v1/reports/',
            data={},
            content_type='application/json',
            **auth_headers
        )
        assert response.status_code == 400
    
    def test_create_report_success(self, api_client, user, auth_headers):
        """Should create report and return tracking code."""
        response = api_client.post(
            '/api/v1/reports/',
            data={
                'type': 'lost',
                'gender': 'male',
                'person_name': 'علی',
                'age': 5,
                'location': {
                    'latitude': 34.6416,
                    'longitude': 50.8746,
                    'address': 'عمود ۸۰'
                },
                'contact_phone': '+989123456789',
                'description': 'کودک گمشده',
            },
            content_type='application/json',
            **auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data['success'] is True
        assert 'tracking_code' in data
        assert data['tracking_code'].startswith('PYD-')
