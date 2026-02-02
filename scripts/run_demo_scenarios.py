#!/usr/bin/env python3
"""
Demo Scenario Runner - 6-Step Flow

Demonstrates the complete challenge flow:
  1. Bootstrap   → POST /bootstrap
  2. View Order  → GET /orders/{id}
  3. Show KPIs   → GET /kpis/{id}
  4. Detect Risk → POST /detect-deviation/{id}
  5. Agent       → POST /trigger-agent/{id}
  6. Response    → GET /view-response/{id}

Usage:
    python scripts/run_demo_scenarios.py --bootstrap --scenario 1002
    python scripts/run_demo_scenarios.py --all
"""
import argparse
import sys
import os
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bootstrap import SCENARIOS, DEMO_ORDER_IDS

API_URL =  "http://localhost:9001"


# ==================== API CALLS ====================

TIMEOUT = None  # No timeout for debugging

def check_api_health() -> bool:
    """Check if API is running."""
    try:
        resp = requests.get(f"{API_URL}/", timeout=5)
        return resp.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


def bootstrap_data() -> dict:
    """Step 1: POST /bootstrap - seed demo data."""
    try:
        resp = requests.post(f"{API_URL}/bootstrap", timeout=TIMEOUT)
        return resp.json() if resp.status_code == 200 else {"error": resp.text}
    except Exception as e:
        return {"error": str(e)}


def get_order(order_id: int) -> dict:
    """Step 2: GET /orders/{id} - fetch order details."""
    try:
        resp = requests.get(f"{API_URL}/orders/{order_id}", timeout=TIMEOUT)
        return resp.json() if resp.status_code == 200 else {"error": f"Not found: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def get_kpis(order_id: int) -> dict:
    """Step 3: GET /kpis/{id} - calculate KPIs."""
    try:
        resp = requests.get(f"{API_URL}/kpis/{order_id}", timeout=TIMEOUT)
        return resp.json() if resp.status_code == 200 else {"error": f"KPI error: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def detect_risk(order_id: int) -> dict:
    """Step 4: POST /detect-deviation/{id} - detect risk signals."""
    try:
        resp = requests.post(f"{API_URL}/detect-deviation/{order_id}", timeout=TIMEOUT)
        return resp.json() if resp.status_code == 200 else {"error": f"Detection failed: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def trigger_agent(order_id: int) -> dict:
    """Step 5: POST /trigger-agent/{id} - run AI agent."""
    try:
        resp = requests.post(f"{API_URL}/trigger-agent/{order_id}", timeout=TIMEOUT)
        return resp.json() if resp.status_code == 200 else {"error": f"Agent failed: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def get_response(order_id: int) -> dict:
    """Step 6: GET /view-response/{id} - view agent actions."""
    try:
        resp = requests.get(f"{API_URL}/view-response/{order_id}", timeout=TIMEOUT)
        return resp.json() if resp.status_code == 200 else {"error": f"No response: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# ==================== SCENARIO RUNNER ====================

def run_scenario(order_id: int, skip_agent: bool = False) -> dict:
    """Run complete 6-step scenario through API endpoints."""
    scenario = SCENARIOS.get(order_id, {})
    scenario_name = scenario.get("name", "Unknown")
    scenario_desc = scenario.get("description", "")
    
    print(f"\n{'='*65}")
    print(f"SCENARIO {order_id}: {scenario_name}")
    print(f"  {scenario_desc}")
    print('='*65)
    
    result = {"order_id": order_id, "success": False}
    
    # Step 2: View Order
    print("\n2️⃣  VIEW ORDER (GET /orders/{id})")
    order = get_order(order_id)
    if "error" in order:
        print(f"   ✗ {order['error']}")
        result["error"] = order["error"]
        return result
    print(f"   Route: {order.get('origin_region')} → {order.get('destination_region')} via {order.get('mode_of_shipment')}")
    print(f"   Customer: Rating={order.get('customer_rating')}, Calls={order.get('customer_care_calls')}")
    print(f"   Ticket Raised: {'Yes' if order.get('ticket_raised') else 'No'}")
    
    # Step 3: Show KPIs
    print("\n3️⃣  CALCULATE KPIs (GET /kpis/{id})")
    kpis_response = get_kpis(order_id)
    if "error" in kpis_response:
        print(f"   ✗ {kpis_response['error']}")
    else:
        kpis = kpis_response.get("kpis", {})
        print("   KPI Values:")
        print(f"      hub_hours:          {kpis.get('hub_hours', 0):.1f}h")
        print(f"      transit_days:       {kpis.get('transit_days', 0)}d")
        print(f"      days_remaining:     {kpis.get('days_remaining', 0)}d")
        print(f"      route_failure_rate: {kpis.get('route_failure_rate', 0):.1%}")
        
        breaches = kpis_response.get("breaches", [])
        if breaches:
            print(f"   ⚠️  Breaches: {', '.join(breaches)}")
    
    # Step 4: Detect Risk
    print("\n4️⃣  DETECT RISK (POST /detect-deviation/{id})")
    detection = detect_risk(order_id)
    if "error" in detection:
        print(f"   ✗ {detection['error']}")
        result["error"] = detection["error"]
        return result
    
    signal_type = detection.get("signal_type", "UNKNOWN")
    severity = detection.get("severity", "UNKNOWN")
    reason = detection.get("reason", "")
    has_risk = detection.get("has_risk", False)
    
    if not has_risk:
        print(f"   ✅ {signal_type}: {reason}")
        result["status"] = "no_risk"
        result["success"] = True
        return result
    
    print(f"   ⚠️  [{severity}] {signal_type}")
    print(f"      {reason}")
    
    result["signal_type"] = signal_type
    
    if skip_agent:
        result["status"] = "detection_only"
        result["success"] = True
        return result
    
    # Step 5: Trigger Agent
    print("\n5️⃣  TRIGGER AGENT (POST /trigger-agent/{id})")
    start = time.time()
    agent_result = trigger_agent(order_id)
    elapsed = time.time() - start
    
    if agent_result.get("error"):
        print(f"   ✗ {agent_result['error']}")
        result["error"] = agent_result["error"]
        return result
    
    status = agent_result.get("status", "unknown")
    message = agent_result.get("message", "")
    print(f"   ✓ Status: {status} ({elapsed:.1f}s)")
    if message:
        print(f"   📝 {message}")
    
    # Step 6: View Response
    print("\n6️⃣  VIEW RESPONSE (GET /view-response/{id})")
    response = get_response(order_id)
    if "error" not in response:
        conversation = response.get("conversation")
        if conversation:
            turns = conversation.get("turns", [])
            print(f"   ✓ Conversation: {len(turns)} turn(s)")
            for t in turns[:5]:
                print(f"      [{t.get('role')}] {t.get('message', '')[:50]}...")
        else:
            print("   (No conversation yet)")
    
    result["status"] = status
    result["success"] = status in ["resolved", "no_risk", "pending_agent"]
    result["execution_time"] = elapsed
    
    return result


def main():
    global API_URL
    
    parser = argparse.ArgumentParser(description="6-Step Demo Flow for Celonis Garage Challenge")
    parser.add_argument("--scenario", type=int, help="Run specific scenario (1001-1004)")
    parser.add_argument("--all", action="store_true", help="Run all 4 scenarios")
    parser.add_argument("--bootstrap", action="store_true", help="Step 1: Bootstrap demo data")
    parser.add_argument("--detect-only", action="store_true", help="Skip agent (steps 1-4 only)")
    parser.add_argument("--url", type=str, default=API_URL, help=f"API URL (default: {API_URL})")
    args = parser.parse_args()
    
    API_URL = args.url
    
    print("=" * 65)
    print("CELONIS GARAGE - PROACTIVE LOGISTICS AGENT DEMO")
    print("=" * 65)
    print(f"\nAPI: {API_URL}")
    
    # Check API
    if not check_api_health():
        print("\n❌ API not responding! Start with:")
        print("   docker-compose up -d")
        sys.exit(1)
    print("✓ API is online")
    
    # Step 1: Bootstrap
    if args.bootstrap:
        print("\n1️⃣  BOOTSTRAP (POST /bootstrap)")
        result = bootstrap_data()
        if "error" not in result:
            print(f"   ✓ {result.get('message', 'Demo data seeded')}")
        else:
            print(f"   ✗ {result['error']}")
    
    # Determine scenarios
    scenarios = [args.scenario] if args.scenario else DEMO_ORDER_IDS
    
    # Run each scenario
    results = {}
    for order_id in scenarios:
        try:
            results[order_id] = run_scenario(order_id, skip_agent=args.detect_only)
        except Exception as e:
            print(f"\n❌ Error in scenario {order_id}: {e}")
            results[order_id] = {"error": str(e), "success": False}
    
    # Summary
    print(f"\n{'='*65}")
    print("SUMMARY")
    print('='*65)
    
    for order_id, r in results.items():
        icon = "✓" if r.get("success") else "✗"
        status = r.get("status", r.get("error", "unknown"))[:25]
        print(f"  {icon} {order_id}: {status}")
    
    success = sum(1 for r in results.values() if r.get("success"))
    print(f"\nTotal: {success}/{len(results)} successful")
    
    return results


if __name__ == "__main__":
    main()
