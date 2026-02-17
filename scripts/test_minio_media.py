#!/usr/bin/env python3
"""
Test script for MinIO/S3 media operations.

Tests all 3 use cases:
1. PUT presigned URL - upload media
2. GET presigned URL - retrieve report images
3. Media verification

Usage:
    python scripts/test_minio_media.py
"""
import os
import sys
import requests
import json

API_BASE = os.environ.get('API_BASE', 'http://localhost:8060/api/v1')
MINIO_EXTERNAL = os.environ.get('MINIO_EXTERNAL', 'http://localhost:9000')

TEST_IMAGE = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'


def get_auth_token():
    """Get auth token by sending OTP and verifying."""
    print("\n=== Getting Auth Token ===")
    
    phone = "9123456789"
    
    resp = requests.post(f"{API_BASE}/auth/send-otp", json={
        "phone": phone,
        "country_code": "+98"
    })
    
    if resp.status_code != 200:
        print(f"Failed to send OTP: {resp.status_code} - {resp.text}")
        return None
    
    data = resp.json()
    request_id = data.get('request_id')
    print(f"OTP sent, request_id: {request_id}")
    
    otp = input("Enter OTP (or press Enter for dev mode '123456'): ").strip() or "123456"
    
    resp = requests.post(f"{API_BASE}/auth/verify-otp", json={
        "request_id": request_id,
        "otp": otp
    })
    
    if resp.status_code != 200:
        print(f"Failed to verify OTP: {resp.status_code} - {resp.text}")
        return None
    
    data = resp.json()
    token = data.get('token')
    print(f"Auth successful, token: {token[:20]}...")
    return token


def test_presigned_put(token):
    """Test 1: Create presigned PUT URL and upload media."""
    print("\n=== Test 1: Presigned PUT URL ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.post(f"{API_BASE}/media", json={
        "filename": "test_image.png",
        "content_type": "image/png",
        "file_size": len(TEST_IMAGE)
    }, headers=headers)
    
    if resp.status_code != 201:
        print(f"FAIL: Create media failed: {resp.status_code} - {resp.text}")
        return None
    
    data = resp.json()
    media_id = data.get('media_id')
    upload_url = data.get('upload_url')
    
    print(f"Media ID: {media_id}")
    print(f"Upload URL: {upload_url[:80]}...")
    
    print("\nUploading file to presigned URL...")
    upload_resp = requests.put(
        upload_url,
        data=TEST_IMAGE,
        headers={"Content-Type": "image/png"}
    )
    
    if upload_resp.status_code not in (200, 204):
        print(f"FAIL: Upload failed: {upload_resp.status_code} - {upload_resp.text}")
        return None
    
    print(f"SUCCESS: File uploaded (status {upload_resp.status_code})")
    return media_id


def test_verify_media(token, media_id):
    """Test 2: Verify uploaded media."""
    print("\n=== Test 2: Verify Media ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.post(f"{API_BASE}/media/{media_id}/verify", headers=headers)
    
    if resp.status_code != 200:
        print(f"FAIL: Verify failed: {resp.status_code} - {resp.text}")
        return False
    
    data = resp.json()
    print(f"Verification result: {json.dumps(data, indent=2)}")
    
    if data.get('status') == 'verified':
        print("SUCCESS: Media verified")
        return True
    else:
        print(f"FAIL: Unexpected status: {data.get('status')}")
        return False


def test_presigned_get(token, media_id):
    """Test 3: Create report with media and get presigned GET URLs."""
    print("\n=== Test 3: Presigned GET URL (via Report) ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Creating report with media...")
    resp = requests.post(f"{API_BASE}/reports", json={
        "type": "lost",
        "gender": "male",
        "person_name": "Test Person",
        "age": 25,
        "description": "Test description for media test",
        "location": {
            "latitude": 34.6416,
            "longitude": 50.8746,
            "address": "Test address"
        },
        "media_ids": [media_id]
    }, headers=headers)
    
    if resp.status_code != 201:
        print(f"FAIL: Create report failed: {resp.status_code} - {resp.text}")
        return False
    
    data = resp.json()
    report_id = data.get('report', {}).get('id')
    print(f"Report created: {report_id}")
    
    print("\nFetching report to get presigned GET URLs...")
    resp = requests.get(f"{API_BASE}/reports/{report_id}", headers=headers)
    
    if resp.status_code != 200:
        print(f"FAIL: Get report failed: {resp.status_code} - {resp.text}")
        return False
    
    data = resp.json()
    image_urls = data.get('report', {}).get('image_urls', [])
    
    if not image_urls:
        print("FAIL: No image URLs in report")
        return False
    
    print(f"Image URLs: {json.dumps(image_urls, indent=2)}")
    
    for i, url in enumerate(image_urls):
        if 'X-Amz-Signature' in url or 'Signature=' in url:
            print(f"SUCCESS: URL {i+1} is a presigned URL")
            
            print(f"\nTesting download from presigned URL...")
            download_resp = requests.get(url)
            if download_resp.status_code == 200:
                print(f"SUCCESS: Downloaded {len(download_resp.content)} bytes")
            else:
                print(f"FAIL: Download failed: {download_resp.status_code}")
                return False
        else:
            print(f"FAIL: URL {i+1} is not a presigned URL: {url[:50]}...")
            return False
    
    return True


def test_cors():
    """Test CORS headers on MinIO."""
    print("\n=== Test CORS ===")
    
    resp = requests.options(
        f"{MINIO_EXTERNAL}/peyda-media/test",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "Content-Type"
        }
    )
    
    print(f"CORS preflight status: {resp.status_code}")
    print(f"CORS headers: {dict(resp.headers)}")
    
    cors_origin = resp.headers.get('Access-Control-Allow-Origin')
    if cors_origin:
        print(f"SUCCESS: CORS enabled, Allow-Origin: {cors_origin}")
        return True
    else:
        print("WARNING: CORS may not be configured on MinIO")
        print("You may need to configure CORS via mc command:")
        print('  mc admin config set myminio api cors_allow_origin="*"')
        return False


def main():
    print("=" * 60)
    print("MinIO/S3 Media Test Script")
    print("=" * 60)
    
    token = get_auth_token()
    if not token:
        print("\nFailed to get auth token. Exiting.")
        sys.exit(1)
    
    media_id = test_presigned_put(token)
    if not media_id:
        print("\nTest 1 (Presigned PUT) failed. Exiting.")
        sys.exit(1)
    
    if not test_verify_media(token, media_id):
        print("\nTest 2 (Verify Media) failed. Exiting.")
        sys.exit(1)
    
    if not test_presigned_get(token, media_id):
        print("\nTest 3 (Presigned GET) failed. Exiting.")
        sys.exit(1)
    
    test_cors()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
