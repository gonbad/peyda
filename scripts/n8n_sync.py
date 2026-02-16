#!/usr/bin/env python3
"""
n8n Workflow Sync Script

This script provides two main operations:
1. Export: Download workflows from n8n and save to JSON files (for version control)
2. Import: Upload workflows from JSON files to n8n (for deployment)

Usage:
    # Export all workflows to backend/n8n_workflows/
    python scripts/n8n_sync.py export

    # Import all workflows from backend/n8n_workflows/
    python scripts/n8n_sync.py import

    # Export/Import specific workflow
    python scripts/n8n_sync.py export --workflow "Welcome Message"
    python scripts/n8n_sync.py import --file welcome_message.json

Environment Variables:
    N8N_API_URL: n8n API URL (default: http://localhost:5678/api/v1)
    N8N_API_KEY: n8n API key (required)

Pre-commit Hook:
    Add to .git/hooks/pre-commit:
    #!/bin/bash
    python scripts/n8n_sync.py export
    git add backend/n8n_workflows/*.json

Deploy Hook:
    Run during deployment:
    python scripts/n8n_sync.py import
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Configuration
DEFAULT_N8N_URL = "http://localhost:5678/api/v1"
WORKFLOWS_DIR = Path(__file__).parent.parent / "backend" / "n8n_workflows"


def get_api_key() -> str:
    """Get n8n API key from environment."""
    api_key = os.environ.get("N8N_API_KEY")
    if not api_key:
        print("Error: N8N_API_KEY environment variable is required")
        print("Generate one in n8n: Settings → API → Create API Key")
        sys.exit(1)
    return api_key


def get_api_url() -> str:
    """Get n8n API URL from environment."""
    return os.environ.get("N8N_API_URL", DEFAULT_N8N_URL)


def slugify(name: str) -> str:
    """Convert workflow name to filename."""
    slug = name.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '_', slug)
    return slug.strip('_')


class N8nClient:
    """Client for n8n API operations."""
    
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip('/')
        self.headers = {
            "X-N8N-API-KEY": api_key,
            "Content-Type": "application/json"
        }
    
    def list_workflows(self) -> List[Dict]:
        """List all workflows."""
        response = requests.get(
            f"{self.api_url}/workflows",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    def get_workflow(self, workflow_id: str) -> Dict:
        """Get a specific workflow by ID."""
        response = requests.get(
            f"{self.api_url}/workflows/{workflow_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def create_workflow(self, workflow: Dict) -> Dict:
        """Create a new workflow."""
        # Remove id if present (n8n will assign new one)
        workflow_data = {k: v for k, v in workflow.items() if k != 'id'}
        
        response = requests.post(
            f"{self.api_url}/workflows",
            headers=self.headers,
            json=workflow_data
        )
        response.raise_for_status()
        return response.json()
    
    def update_workflow(self, workflow_id: str, workflow: Dict) -> Dict:
        """Update an existing workflow."""
        response = requests.put(
            f"{self.api_url}/workflows/{workflow_id}",
            headers=self.headers,
            json=workflow
        )
        response.raise_for_status()
        return response.json()
    
    def find_workflow_by_name(self, name: str) -> Optional[Dict]:
        """Find a workflow by name."""
        workflows = self.list_workflows()
        for wf in workflows:
            if wf.get("name") == name:
                return wf
        return None
    
    def activate_workflow(self, workflow_id: str) -> None:
        """Activate a workflow."""
        response = requests.patch(
            f"{self.api_url}/workflows/{workflow_id}",
            headers=self.headers,
            json={"active": True}
        )
        response.raise_for_status()
    
    def deactivate_workflow(self, workflow_id: str) -> None:
        """Deactivate a workflow."""
        response = requests.patch(
            f"{self.api_url}/workflows/{workflow_id}",
            headers=self.headers,
            json={"active": False}
        )
        response.raise_for_status()


def export_workflows(client: N8nClient, workflow_name: Optional[str] = None) -> None:
    """Export workflows from n8n to JSON files."""
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    
    workflows = client.list_workflows()
    
    if workflow_name:
        workflows = [w for w in workflows if w.get("name") == workflow_name]
        if not workflows:
            print(f"Workflow not found: {workflow_name}")
            sys.exit(1)
    
    exported = 0
    for wf_summary in workflows:
        workflow = client.get_workflow(wf_summary["id"])
        
        # Clean workflow for export (remove runtime-specific fields)
        export_data = {
            "name": workflow["name"],
            "nodes": workflow.get("nodes", []),
            "connections": workflow.get("connections", {}),
            "settings": workflow.get("settings", {}),
            "staticData": workflow.get("staticData"),
            "tags": workflow.get("tags", []),
            "pinData": workflow.get("pinData", {}),
            "versionId": workflow.get("versionId", "1")
        }
        
        filename = slugify(workflow["name"]) + ".json"
        filepath = WORKFLOWS_DIR / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported: {workflow['name']} → {filename}")
        exported += 1
    
    print(f"\nExported {exported} workflow(s) to {WORKFLOWS_DIR}")


def import_workflows(client: N8nClient, filename: Optional[str] = None) -> None:
    """Import workflows from JSON files to n8n."""
    if not WORKFLOWS_DIR.exists():
        print(f"Workflows directory not found: {WORKFLOWS_DIR}")
        sys.exit(1)
    
    if filename:
        files = [WORKFLOWS_DIR / filename]
        if not files[0].exists():
            print(f"File not found: {files[0]}")
            sys.exit(1)
    else:
        files = list(WORKFLOWS_DIR.glob("*.json"))
    
    imported = 0
    for filepath in files:
        with open(filepath, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        
        workflow_name = workflow.get("name")
        if not workflow_name:
            print(f"Skipping {filepath.name}: no name field")
            continue
        
        # Check if workflow exists
        existing = client.find_workflow_by_name(workflow_name)
        
        if existing:
            # Update existing workflow
            # First deactivate to allow updates
            try:
                client.deactivate_workflow(existing["id"])
            except Exception:
                pass
            
            client.update_workflow(existing["id"], workflow)
            print(f"Updated: {workflow_name}")
        else:
            # Create new workflow
            client.create_workflow(workflow)
            print(f"Created: {workflow_name}")
        
        imported += 1
    
    print(f"\nImported {imported} workflow(s)")


def main():
    parser = argparse.ArgumentParser(
        description="Sync n8n workflows with local JSON files"
    )
    parser.add_argument(
        "action",
        choices=["export", "import"],
        help="Action to perform"
    )
    parser.add_argument(
        "--workflow",
        help="Specific workflow name (for export)"
    )
    parser.add_argument(
        "--file",
        help="Specific file name (for import)"
    )
    
    args = parser.parse_args()
    
    api_url = get_api_url()
    api_key = get_api_key()
    
    client = N8nClient(api_url, api_key)
    
    # Test connection
    try:
        client.list_workflows()
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to n8n at {api_url}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"Error: API request failed: {e}")
        sys.exit(1)
    
    if args.action == "export":
        export_workflows(client, args.workflow)
    elif args.action == "import":
        import_workflows(client, args.file)


if __name__ == "__main__":
    main()
