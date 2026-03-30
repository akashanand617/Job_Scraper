"""
DynamoDB helpers for the Auto-Apply module.
Provides CRUD operations for users, profiles, and applications.
Falls back to local JSON storage when DynamoDB is unavailable.
"""

import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

USERS_TABLE = os.getenv("USERS_TABLE", "job-scraper-users")
PROFILES_TABLE = os.getenv("PROFILES_TABLE", "job-scraper-profiles")
APPLICATIONS_TABLE = os.getenv("APPLICATIONS_TABLE", "job-scraper-applications")
LOCAL_STORAGE_DIR = os.getenv("APPLY_STORAGE_DIR", "/tmp/apply_data")


def _dynamodb_resource():
    """Get DynamoDB resource, or None if unavailable."""
    try:
        import boto3
        return boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    except Exception:
        return None


def _ensure_local_dirs():
    """Create local storage directories."""
    for subdir in ["users", "profiles", "applications"]:
        os.makedirs(os.path.join(LOCAL_STORAGE_DIR, subdir), exist_ok=True)


# ---------------------------------------------------------------------------
# Generic DynamoDB Operations (with local fallback)
# ---------------------------------------------------------------------------

def put_item(table_name: str, item: Dict[str, Any]) -> bool:
    """Put an item into DynamoDB (or local JSON fallback)."""
    dynamo = _dynamodb_resource()
    if dynamo:
        try:
            table = dynamo.Table(table_name)
            table.put_item(Item=item)
            return True
        except Exception as e:
            print(f"DynamoDB put_item failed for {table_name}: {e}")

    # Local fallback
    _ensure_local_dirs()
    subdir = _table_to_subdir(table_name)
    key = _item_key(table_name, item)
    path = os.path.join(LOCAL_STORAGE_DIR, subdir, f"{key}.json")
    with open(path, "w") as f:
        json.dump(item, f, indent=2, default=str)
    return True


def get_item(table_name: str, key: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Get an item from DynamoDB by primary key."""
    dynamo = _dynamodb_resource()
    if dynamo:
        try:
            table = dynamo.Table(table_name)
            response = table.get_item(Key=key)
            return response.get("Item")
        except Exception as e:
            print(f"DynamoDB get_item failed for {table_name}: {e}")

    # Local fallback
    _ensure_local_dirs()
    subdir = _table_to_subdir(table_name)
    key_str = "_".join(key.values())
    path = os.path.join(LOCAL_STORAGE_DIR, subdir, f"{key_str}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None


def query_items(table_name: str, key_name: str, key_value: str) -> List[Dict[str, Any]]:
    """Query items by partition key."""
    dynamo = _dynamodb_resource()
    if dynamo:
        try:
            from boto3.dynamodb.conditions import Key
            table = dynamo.Table(table_name)
            response = table.query(
                KeyConditionExpression=Key(key_name).eq(key_value)
            )
            return response.get("Items", [])
        except Exception as e:
            print(f"DynamoDB query failed for {table_name}: {e}")

    # Local fallback: scan all files in subdir and filter
    _ensure_local_dirs()
    subdir = _table_to_subdir(table_name)
    items_dir = os.path.join(LOCAL_STORAGE_DIR, subdir)
    results = []
    if os.path.exists(items_dir):
        for filename in os.listdir(items_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(items_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        item = json.load(f)
                    if item.get(key_name) == key_value:
                        results.append(item)
                except Exception:
                    continue
    return results


def delete_item(table_name: str, key: Dict[str, str]) -> bool:
    """Delete an item from DynamoDB."""
    dynamo = _dynamodb_resource()
    if dynamo:
        try:
            table = dynamo.Table(table_name)
            table.delete_item(Key=key)
            return True
        except Exception as e:
            print(f"DynamoDB delete_item failed for {table_name}: {e}")

    # Local fallback
    _ensure_local_dirs()
    subdir = _table_to_subdir(table_name)
    key_str = "_".join(key.values())
    path = os.path.join(LOCAL_STORAGE_DIR, subdir, f"{key_str}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def scan_items(table_name: str) -> List[Dict[str, Any]]:
    """Scan all items in a table (use sparingly)."""
    dynamo = _dynamodb_resource()
    if dynamo:
        try:
            table = dynamo.Table(table_name)
            response = table.scan()
            return response.get("Items", [])
        except Exception as e:
            print(f"DynamoDB scan failed for {table_name}: {e}")

    # Local fallback
    _ensure_local_dirs()
    subdir = _table_to_subdir(table_name)
    items_dir = os.path.join(LOCAL_STORAGE_DIR, subdir)
    results = []
    if os.path.exists(items_dir):
        for filename in os.listdir(items_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(items_dir, filename), "r") as f:
                        results.append(json.load(f))
                except Exception:
                    continue
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _table_to_subdir(table_name: str) -> str:
    """Map table name to local storage subdirectory."""
    mapping = {
        USERS_TABLE: "users",
        PROFILES_TABLE: "profiles",
        APPLICATIONS_TABLE: "applications",
    }
    return mapping.get(table_name, "misc")


def _item_key(table_name: str, item: Dict[str, Any]) -> str:
    """Extract a filesystem-safe key string from an item."""
    if table_name == USERS_TABLE:
        return item.get("api_key", "unknown")
    elif table_name == PROFILES_TABLE:
        return item.get("user_id", "unknown")
    elif table_name == APPLICATIONS_TABLE:
        return f"{item.get('user_id', 'unknown')}_{item.get('job_id', 'unknown')}"
    return "unknown"
