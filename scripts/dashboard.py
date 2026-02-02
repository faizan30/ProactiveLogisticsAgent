#!/usr/bin/env python3
"""
Streamlit Dashboard for Celonis Garage Proactive Logistics Agent.

Two demo flows:
- Flow 1: Individual Scenarios (manual step-by-step)
- Flow 2: Scheduler Scenarios (automated batch processing)

Usage:
    streamlit run scripts/dashboard.py
"""
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.bootstrap import DEMO_ORDER_IDS, SCENARIO_DESCRIPTIONS, SCHEDULER_DEMO_IDS

API_URL = os.getenv("API_URL", "http://localhost:9001")

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

def add_log(msg):
    """Add message to scheduler log."""
    if 'scheduler_logs' not in st.session_state:
        st.session_state.scheduler_logs = []
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.scheduler_logs.append(f"[{timestamp}] {msg}")
    # Keep last 50 entries
    st.session_state.scheduler_logs = st.session_state.scheduler_logs[-50:]

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
    **Flow 1 - Individual:**
    1. Bootstrap data
    2. Select scenario
    3. Show Data → Detect → Agent → Response
    
    **Flow 2 - Scheduler:**
    1. Bootstrap scheduler data
    2. Start scheduler
    3. Watch automated processing
    """)
    
    st.divider()
    
    # Scenario Reference
    st.subheader("🎯 4 Core Scenarios")
    st.markdown("""
    | ID | Scenario |
    |----|----------|
    | 901 | ✅ Happy Path |
    | 902 | ⚠️ Predicted Delay |
    | 903 | 📦 Warehouse (36h) |
    | 904 | 👻 Ghost (60h) |
    """)
    
    st.divider()
    
    st.info("""
    **Key Insight**
    
    Deterministic detection,
    Probabilistic resolution.
    """)

# ============================================================
# MAIN: TWO TABS
# ============================================================
tab1, tab2 = st.tabs(["🎯 Flow 1: Individual Scenarios", "⏰ Flow 2: Scheduler"])

# ============================================================
# TAB 1: INDIVIDUAL SCENARIOS
# ============================================================
with tab1:
    # Header with Bootstrap
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.header("Individual Scenario Testing")
    with col_h2:
        if st.button("🔄 Bootstrap Data", type="secondary", use_container_width=True):
            with st.spinner("Seeding..."):
                res = requests.post(f"{API_URL}/bootstrap")
                if res.status_code == 200:
                    st.toast("✅ Demo data seeded!")
                    st.session_state.bootstrapped = True
    
    st.divider()
    
    # Scenario Selector - Compact single row
    st.subheader("Select Scenario")
    
    scenarios = {
        901: ("✅ Happy", "No risk - order on track"),
        902: ("⚠️ Delay", "Email → Customer requests refund → Refund issued"),
        903: ("📦 Warehouse", "Stuck 36h → Ping ops → Dispatched → Re-check resolved"),
        904: ("👻 Ghost", "At hub 60h → Ping manager → Customer reschedules"),
    }
    
    # Single row of buttons
    cols = st.columns(len(scenarios))
    selected = st.session_state.get('selected_order', 901)
    
    for i, (oid, (label, _)) in enumerate(scenarios.items()):
        with cols[i]:
            btn_type = "primary" if oid == selected else "secondary"
            if st.button(label, key=f"s{oid}", type=btn_type, use_container_width=True):
                st.session_state.selected_order = oid
                st.session_state.detection_result = None
                st.session_state.agent_result = None
                st.rerun()
    
    # Expandable description
    selected = st.session_state.get('selected_order', 901)
    with st.expander(f"📝 Order {selected}: {scenarios[selected][0]}", expanded=False):
        st.markdown(f"**Description:** {scenarios[selected][1]}")
        st.markdown(f"**Expected Signal:** `{SCENARIO_DESCRIPTIONS.get(selected, 'N/A')}`")
    
    st.divider()
    
    # Action Buttons Row - 6-Step Demo Flow
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
    
    # Results Area
    results_area = st.container()
    
    with results_area:
        # Handle button clicks
        if show_data:
            st.subheader(f"2️⃣ Order {selected} Data")
            data = get_order_data(selected)
            if data:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown("**📍 Route**")
                    st.write(f"{data.get('Origin_Region', '?')} → {data.get('Destination_Region', '?')}")
                    st.write(f"Mode: {data.get('Mode_of_Shipment', 'N/A')}")
                with col2:
                    st.markdown("**📅 Dates**")
                    st.write(f"Order: {str(data.get('Order_Date', 'N/A'))[:10]}")
                    st.write(f"Promised: {str(data.get('Promised_Date', 'N/A'))[:10]}")
                    st.write(f"Shipped: {str(data.get('Ship_Date', 'N/A'))[:10]}")
                with col3:
                    st.markdown("**👤 Customer**")
                    st.write(f"Rating: {data.get('Customer_rating', 'N/A')} ⭐")
                    st.write(f"Care Calls: {data.get('Customer_care_calls', 0)}")
            else:
                st.warning("Order not found. Click Bootstrap first.")
        
        if show_kpis:
            st.subheader(f"3️⃣ KPIs for Order {selected}")
            kpis = get_kpis(selected)
            if kpis and 'kpis' in kpis:
                kpi_vals = kpis['kpis']
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**⏱️ Fulfillment Gaps** (hours)")
                    st.write(f"• Warehouse: **{kpi_vals.get('gap_warehouse', 0):.1f}h**")
                    st.write(f"• Transit: **{kpi_vals.get('gap_transit', 0):.1f}h**")
                    st.write(f"• Last-Mile: **{kpi_vals.get('gap_lastmile', 0):.1f}h**")
                with c2:
                    st.markdown("**📊 Risk Scores** (0-1)")
                    delay = kpi_vals.get('delay_likelihood', 0)
                    delay_status = "🔴" if delay > 0.7 else "🟡" if delay > 0.3 else "🟢"
                    st.write(f"• Delay Likelihood: **{delay:.0%}** {delay_status}")
                    frust = kpi_vals.get('customer_frustration', 0)
                    frust_status = "🔴" if frust > 0.7 else "🟡" if frust > 0.3 else "🟢"
                    st.write(f"• Customer Frustration: **{frust:.0%}** {frust_status}")
                    route = kpi_vals.get('route_risk', 0)
                    st.write(f"• Route Risk: **{route:.0%}**")
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
                        for sig in result.get('signals', []):
                            sev = sig.get('severity', 'MEDIUM')
                            sev_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(sev, "⚪")
                            sig_type = sig.get('signal_type', 'UNKNOWN').replace('_', ' ').title()
                            st.markdown(f"{sev_icon} **{sig_type}** ({sev})")
                            st.caption(sig.get('description', ''))
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
                    
                    if result.get('action_taken'):
                        st.markdown(f"**Action:** {result['action_taken']}")
                    
                    trace = result.get('trace', [])
                    if trace:
                        with st.expander("📜 Trace", expanded=True):
                            for i, step in enumerate(trace, 1):
                                st.markdown(f"{i}. {step}")
                else:
                    st.error(f"Error: {res.text}")
        
        if show_response:
            st.subheader(f"6️⃣ Stored Response for Order {selected}")
            actions = get_order_actions(selected)
            if actions and actions.get('actions'):
                for action in actions['actions']:
                    st.json(action)
            else:
                st.info("No actions recorded yet. Trigger agent first.")

# ============================================================
# TAB 2: SCHEDULER
# ============================================================
with tab2:
    st.header("Scheduler Demo")
    st.caption("Automated batch processing with scheduler scenarios (911-914)")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("🛠️ Setup")
        
        # Bootstrap scheduler data
        if st.button("� Bootstrap Scheduler Data", use_container_width=True):
            with st.spinner("Seeding scheduler scenarios..."):
                res = requests.post(f"{API_URL}/bootstrap")
                if res.status_code == 200:
                    add_log("✅ Scheduler data bootstrapped (911-914)")
                    st.toast("Data ready!")
                    st.rerun()
        
        st.divider()
        
        # Scheduler Status
        st.subheader("⏰ Scheduler")
        try:
            sched_res = requests.get(f"{API_URL}/scheduler/status", timeout=2)
            if sched_res.status_code == 200:
                sched = sched_res.json()
                if sched.get('enabled'):
                    is_paused = sched.get('paused', False)
                    
                    if is_paused:
                        st.warning("⏸️ Paused")
                    else:
                        st.success("▶️ Running")
                        st.caption(f"Interval: {sched.get('interval', 'N/A')}")
                        if sched.get('next_run'):
                            st.caption(f"Next: {sched['next_run'][:19]}")
                    
                    # Control buttons
                    if is_paused:
                        if st.button("▶️ Resume", use_container_width=True):
                            requests.post(f"{API_URL}/scheduler/resume")
                            add_log("▶️ Scheduler resumed")
                            st.rerun()
                    else:
                        if st.button("⏸️ Pause", use_container_width=True):
                            requests.post(f"{API_URL}/scheduler/pause")
                            add_log("⏸️ Scheduler paused")
                            st.rerun()
                    
                    if st.button("🔄 Run Now", type="primary", use_container_width=True):
                        with st.spinner("Running batch..."):
                            res = requests.post(f"{API_URL}/scheduler/trigger", timeout=30)
                            if res.status_code == 200:
                                result = res.json().get('result', {})
                                scanned = result.get('orders_scanned', 0)
                                found = result.get('deviations_found', 0)
                                add_log(f"🔄 Batch: {scanned} scanned, {found} risks")
                                st.session_state.last_batch = result
                                st.rerun()
                else:
                    st.info("🔴 Scheduler disabled")
                    st.caption("Set SCHEDULER_ENABLED=true in .env")
        except Exception as e:
            st.error(f"Cannot connect: {e}")
        
        st.divider()
        
        # Scheduler scenarios info
        st.subheader("📋 Scheduler Orders")
        st.markdown("""
        | ID | Scenario |
        |----|----------|
        | 911 | Predicted Delay |
        | 912 | Warehouse Stagnation |
        | 913 | Ghost Delivery |
        | 914 | Happy Path |
        """)
    
    with col2:
        st.subheader("📜 Activity Log")
        
        # Log container
        log_container = st.container(height=400)
        
        with log_container:
            if 'scheduler_logs' in st.session_state and st.session_state.scheduler_logs:
                for log in reversed(st.session_state.scheduler_logs):
                    st.text(log)
            else:
                st.caption("No activity yet. Bootstrap data and run scheduler.")
        
        # Last batch results
        if 'last_batch' in st.session_state:
            st.divider()
            st.subheader("📊 Last Batch Result")
            batch = st.session_state.last_batch
            
            m1, m2 = st.columns(2)
            m1.metric("Orders Scanned", batch.get('orders_scanned', 0))
            m2.metric("Risks Found", batch.get('deviations_found', 0))
            
            signals = batch.get('signals', [])
            if signals:
                df = pd.DataFrame(signals)
                display_cols = [c for c in ['order_id', 'signal_type', 'severity'] if c in df.columns]
                st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
