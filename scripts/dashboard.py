#!/usr/bin/env python3
"""
Streamlit Dashboard for Celonis Garage Proactive Logistics Agent.

Usage:
    streamlit run scripts/dashboard.py
"""
import streamlit as st
import requests
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.bootstrap import SCENARIOS

API_URL = os.getenv("API_URL", "http://127.0.0.1:9001")

st.set_page_config(
    page_title="Proactive Logistics Agent", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# HELPERS
# ============================================================
def api_ok():
    try:
        return requests.get(f"{API_URL}/", timeout=2).status_code == 200
    except:
        return False

def get_order_data(order_id):
    """Fetch order from DB."""
    try:
        res = requests.get(f"{API_URL}/orders/{order_id}", timeout=5)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def get_order_actions(order_id):
    """Fetch agent actions for order."""
    try:
        res = requests.get(f"{API_URL}/view-response/{order_id}", timeout=5)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def get_kpis(order_id):
    """Fetch KPIs for order."""
    try:
        res = requests.get(f"{API_URL}/kpis/{order_id}", timeout=5)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title("🚛 Logistics Agent")
    
    # Connection status
    if api_ok():
        st.success("✅ API Connected")
    else:
        st.error("❌ API Offline")
        st.code("docker-compose up -d")
        st.stop()
    
    st.divider()
    
    # Demo Flow Guide
    st.subheader("📖 Demo Flow")
    st.markdown("""
    1. Bootstrap data
    2. Select scenario
    3. Order → KPIs → Detect → Agent → Response
    """)
    
    st.divider()
    
    # Scenario Reference
    st.subheader("🎯 4 Scenarios")
    st.markdown("""
    | ID | Scenario |
    |----|----------|
    | 1001 | ✅ Happy Path |
    | 1002 | ⚠️ Predicted Delay |
    | 1003 | 📦 Stuck at Hub |
    | 1004 | 🎫 Ticket Raised |
    """)
    
    st.divider()
    
    st.info("""
    **Key Insight**
    
    Deterministic detection,
    Probabilistic resolution.
    """)

# ============================================================
# MAIN CONTENT
# ============================================================
# Header with Bootstrap
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.header("Scenario Testing")
with col_h2:
    if st.button("🔄 Bootstrap Data", type="secondary", use_container_width=True):
        with st.spinner("Seeding..."):
            res = requests.post(f"{API_URL}/bootstrap")
            if res.status_code == 200:
                st.toast("✅ Demo data seeded!")
                st.session_state.bootstrapped = True

st.divider()

# Scenario Selector
st.subheader("Select Scenario")

scenarios = {
    1001: ("✅ Happy", "No risk - order on track"),
    1002: ("⚠️ Delay", "Predicted delay → Customer → Refund"),
    1003: ("📦 Hub", "Stuck at hub 60h → Ops → Customer reschedules"),
    1004: ("🎫 Ticket", "Customer complained → Empathy + Refund"),
}

# Single row of buttons
cols = st.columns(len(scenarios))
selected = st.session_state.get('selected_order', 1001)

for i, (oid, (label, _)) in enumerate(scenarios.items()):
    with cols[i]:
        btn_type = "primary" if oid == selected else "secondary"
        if st.button(label, key=f"s{oid}", type=btn_type, use_container_width=True):
            st.session_state.selected_order = oid
            st.session_state.detection_result = None
            st.session_state.agent_result = None
            st.rerun()

# Expandable description
selected = st.session_state.get('selected_order', 1001)
scenario_info = SCENARIOS.get(selected, {})
with st.expander(f"📝 Order {selected}: {scenarios[selected][0]}", expanded=False):
    st.markdown(f"**Description:** {scenarios[selected][1]}")
    st.markdown(f"**Expected Signal:** `{scenario_info.get('expected_signal', 'N/A')}`")

st.divider()

# Action Buttons Row
st.subheader("Demo Steps")
b1, b2, b3, b4, b5 = st.columns(5)

with b1:
    show_data = st.button("2️⃣ Order", use_container_width=True, help="GET /orders/{id}")
with b2:
    show_kpis = st.button("3️⃣ KPIs", use_container_width=True, help="GET /kpis/{id}")
with b3:
    run_detect = st.button("4️⃣ Detect", type="primary", use_container_width=True, help="POST /detect-deviation/{id}")
with b4:
    run_agent = st.button("5️⃣ Agent", type="primary", use_container_width=True, help="POST /trigger-agent/{id}")
with b5:
    show_response = st.button("6️⃣ Response", use_container_width=True, help="GET /view-response/{id}")

st.divider()

# Results Area - Handle button clicks
if show_data:
    st.subheader(f"2️⃣ Order {selected} Data")
    data = get_order_data(selected)
    if data:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**📍 Route**")
            st.write(f"{data.get('origin_region', '?')} → {data.get('destination_region', '?')}")
            st.write(f"Mode: {data.get('mode_of_shipment', 'N/A')}")
        with col2:
            st.markdown("**📅 Dates**")
            st.write(f"Order: {str(data.get('order_date', 'N/A'))[:10]}")
            st.write(f"Promised: {str(data.get('promised_date', 'N/A'))[:10]}")
            st.write(f"Shipped: {str(data.get('ship_date', 'N/A'))[:10]}")
        with col3:
            st.markdown("**👤 Customer**")
            st.write(f"Rating: {data.get('customer_rating', 'N/A')} ⭐")
            st.write(f"Care Calls: {data.get('customer_care_calls', 0)}")
    else:
        st.warning("Order not found. Click Bootstrap first.")

if show_kpis:
    st.subheader(f"3️⃣ KPIs for Order {selected}")
    kpis = get_kpis(selected)
    if kpis and 'kpis' in kpis:
        kpi_vals = kpis['kpis']
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**⏱️ Time Metrics** (hours)")
            st.write(f"• Hub Hours: **{kpi_vals.get('hub_hours', 0):.1f}h**")
            st.write(f"• Transit Hours: **{kpi_vals.get('transit_hours', 0):.1f}h**")
            st.write(f"• Hours Remaining: **{kpi_vals.get('hours_remaining', 0):.1f}h**")
        with c2:
            st.markdown("**📊 Risk Indicators**")
            delay = kpi_vals.get('predicted_delay', 0)
            delay_status = "🔴" if delay > 0.7 else "🟡" if delay > 0.3 else "🟢"
            st.write(f"• Predicted Delay: **{delay:.0%}** {delay_status}")
            route = kpi_vals.get('route_failure_rate', 0)
            st.write(f"• Route Failure Rate: **{route:.0%}**")
            ticket = kpi_vals.get('ticket_raised', 0)
            st.write(f"• Ticket Raised: **{'Yes' if ticket else 'No'}**")
    else:
        st.warning("KPIs not available. Bootstrap first.")

if run_detect:
    st.subheader(f"4️⃣ Risk Detection for Order {selected}")
    with st.spinner("Analyzing..."):
        res = requests.post(f"{API_URL}/detect-deviation/{selected}")
        if res.status_code == 200:
            result = res.json()
            st.session_state.detection_result = result
            
            if result.get('has_risk'):
                severity = result.get('severity', 'MEDIUM')
                sev_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(severity, "⚪")
                sig_type = result.get('signal_type', 'UNKNOWN').replace('_', ' ').title()
                st.markdown(f"{sev_icon} **{sig_type}** ({severity})")
                st.caption(result.get('reason', ''))
            else:
                st.success("✅ No Risk - Order on track")
        else:
            st.error(f"Error: {res.text}")

if run_agent:
    st.subheader(f"5️⃣ Agent Resolution for Order {selected}")
    with st.spinner("Agent working..."):
        res = requests.post(f"{API_URL}/trigger-agent/{selected}", timeout=60)
        if res.status_code == 200:
            result = res.json()
            st.session_state.agent_result = result
            
            status = result.get('status', 'unknown')
            if status == 'awaiting_approval':
                st.warning("🛑 HITL Gate - Awaiting Approval")
            elif status in ['completed', 'resolved']:
                st.success("✅ Resolution Complete")
            elif status == 'no_risk':
                st.info("✅ No action needed")
            else:
                st.info(f"Status: {status}")
            
            actions = result.get('actions_taken', [])
            if actions:
                with st.expander("📜 Actions Taken", expanded=True):
                    for i, action in enumerate(actions, 1):
                        st.markdown(f"{i}. {action}")
        else:
            st.error(f"Error: {res.text}")

if show_response:
    st.subheader(f"6️⃣ Stored Response for Order {selected}")
    response = get_order_actions(selected)
    if response and response.get('conversation'):
        conv = response['conversation']
        st.markdown(f"**Status:** {conv.get('status', 'N/A')}")
        st.markdown(f"**Resolution:** {conv.get('resolution', 'N/A')}")
        
        turns = conv.get('turns', [])
        if turns:
            with st.expander("📜 Conversation Turns", expanded=True):
                for turn in turns:
                    role = turn.get('role', 'unknown')
                    action = turn.get('action', '')
                    msg = turn.get('message', '')[:200]
                    st.markdown(f"**{role.upper()}** ({action}): {msg}")
    else:
        st.info("No actions recorded yet. Trigger agent first.")
