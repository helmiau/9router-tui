#!/usr/bin/env python3
"""
Diagnostic script for 9Router TUI project
Tests all API endpoints to identify working/broken ones
"""

import requests
import json
from typing import Dict, List, Any, Optional
import time

def test_endpoint(base_url: str, endpoint: str, headers: Dict[str, str], 
                  timeout: int = 5, expected_status: int = 200) -> Dict[str, Any]:
    """Test a single endpoint and return results."""
    result = {
        "endpoint": endpoint,
        "status": None,
        "success": False,
        "error": None,
        "response_preview": "",
        "latency_ms": 0
    }
    
    try:
        start = time.time()
        resp = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=timeout)
        result["latency_ms"] = int((time.time() - start) * 1000)
        result["status"] = resp.status_code
        result["success"] = resp.status_code == expected_status
        result["response_preview"] = resp.text[:200] if resp.status_code == 200 else resp.text[:100]
    except requests.exceptions.Timeout:
        result["error"] = "TIMEOUT"
        result["latency_ms"] = timeout * 1000
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"CONNECTION_ERROR: {str(e)[:100]}"
    except Exception as e:
        result["error"] = f"UNKNOWN_ERROR: {str(e)[:100]}"
    
    return result

def main():
    # Configuration
    base_url = "http://10.10.40.10:20128"
    api_key = "sk-fa5f344bf7795553-pkntwa-f563c2ef"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Endpoints to test (from client.py and 9router-master)
    endpoints = [
        # Core endpoints
        "/api/health",
        "/api/version",
        "/api/auth/status",
        "/api/settings",
        
        # Provider endpoints
        "/api/providers",
        "/api/provider-nodes",
        
        # Model endpoints
        "/api/models",
        "/api/models/alias",
        "/api/models/custom",
        "/api/models/disabled",
        "/api/v1/models",
        "/api/v1beta/models",
        
        # Key endpoints
        "/api/keys",
        
        # Combo endpoints
        "/api/combos",
        
        # Usage endpoints (may not exist)
        "/api/usage",
        "/api/usage/stats",
        "/api/usage/chart",
        "/api/usage/history",
        
        # Other endpoints
        "/api/tags",
        "/api/locale",
        "/api/headroom/status",
        "/api/pricing",
        "/api/shutdown",
    ]
    
    print(f"Testing 9Router API endpoints at {base_url}")
    print(f"=" * 60)
    
    results = []
    for ep in endpoints:
        result = test_endpoint(base_url, ep, headers, timeout=3)
        results.append(result)
        
        # Print result
        status = result["status"]
        error = result["error"]
        latency = result["latency_ms"]
        
        if error:
            if error == "TIMEOUT":
                print(f"❌ {ep:<40} TIMEOUT ({latency}ms)")
            else:
                print(f"❌ {ep:<40} ERROR - {error}")
        else:
            if status == 200:
                print(f"✅ {ep:<40} OK ({status}) [{latency}ms]")
            elif status == 404:
                print(f"⚠️  {ep:<40} NOT FOUND ({status})")
            elif status == 401:
                print(f"🔒 {ep:<40} UNAUTHORIZED ({status})")
            else:
                print(f"⚠️  {ep:<40} UNEXPECTED ({status})")
    
    print(f"\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    working = [r for r in results if r["success"]]
    not_found = [r for r in results if r["status"] == 404]
    unauthorized = [r for r in results if r["status"] == 401]
    timeouts = [r for r in results if r["error"] == "TIMEOUT"]
    other_errors = [r for r in results if r["error"] and r["error"] != "TIMEOUT"]
    
    print(f"✅ Working (200): {len(working)}")
    for r in working:
        print(f"   - {r['endpoint']}")
    
    print(f"\n⚠️  Not Found (404): {len(not_found)}")
    for r in not_found:
        print(f"   - {r['endpoint']}")
    
    print(f"\n🔒 Unauthorized (401): {len(unauthorized)}")
    for r in unauthorized:
        print(f"   - {r['endpoint']}")
    
    print(f"\n❌ Timeouts: {len(timeouts)}")
    for r in timeouts:
        print(f"   - {r['endpoint']}")
    
    if other_errors:
        print(f"\n❌ Other Errors: {len(other_errors)}")
        for r in other_errors:
            print(f"   - {r['endpoint']}: {r['error']}")
    
    # Save results to file
    with open("diagnostic_results.json", "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base_url": base_url,
            "results": results
        }, f, indent=2)
    
    print(f"\nResults saved to diagnostic_results.json")

if __name__ == "__main__":
    main()
