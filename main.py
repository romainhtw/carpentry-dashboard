import streamlit as st
import pandas as pd
import plotly.express as px
import google.generativeai as genai
import fitz  # PyMuPDF
import io
import json
from PIL import Image

# Page Configuration
st.set_page_config(page_title="Carpentry Dashboard", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for Construction Dark Mode
st.markdown("""
    <style>
    :root {
        --charcoal: #2A2A2A;
        --darker: #1A1A1A;
        --safety-orange: #FF5F15;
        --neon-green: #39FF14;
        --text-color: #E0E0E0;
    }
    
    .stApp {
        background-color: var(--darker);
        color: var(--text-color);
    }
    
    [data-testid="stSidebar"] {
        background-color: var(--charcoal);
    }
    
    h1, h2, h3 {
        color: var(--safety-orange) !important;
    }
    
    .metric-card {
        background-color: var(--charcoal);
        border-left: 5px solid var(--safety-orange);
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        box-shadow: 0px 4px 6px rgba(0,0,0,0.5);
    }
    
    .green-text {
        color: var(--neon-green);
        font-weight: 700;
    }
    
    .orange-text {
        color: var(--safety-orange);
        font-weight: 700;
    }
    
    .warning-text {
        color: #FF3333;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🚧 Carpentry Profit & Worker Efficiency Dashboard")

# --- State initialization ---
if 'workers' not in st.session_state:
    st.session_state.workers = []
    default_types = ["TFN Full-Time", "TFN Casual", "ABN", "Sponsored", "TFN Full-Time", "TFN Casual", "ABN", "TFN Full-Time"]
    for i in range(8):
        st.session_state.workers.append({
            "name": f"Worker {i+1}",
            "type": default_types[i],
            "base_rate": 35.0 if default_types[i] != "ABN" else 55.0,
            "sponsorship_monthly": 1500.0 if default_types[i] == "Sponsored" else 0.0,
            "charge_rate": 85.0,
            "hours_paid": 40.0,
            "hours_billed": 34.0 if i == 1 else 38.0
        })

if 'transactions' not in st.session_state:
    st.session_state.transactions = []
if 'review_queue' not in st.session_state:
    st.session_state.review_queue = []

# --- Calculator Logic (2026 Standards) ---
def calculate_thc(worker):
    emp_type = worker["type"]
    base = worker["base_rate"]
    
    thc = 0.0
    super_rate = 0.12
    workcover_rate = 0.0182
    provision_rate = 0.15
    casual_loading = 1.25
    monthly_hours = 152
    
    if emp_type == "ABN":
        thc = base
    elif emp_type == "TFN Casual":
        effective_base = base * casual_loading
        super_cost = effective_base * super_rate
        insurance = effective_base * workcover_rate
        thc = effective_base + super_cost + insurance
    elif emp_type == "TFN Full-Time":
        provisioning = base * provision_rate
        super_cost = base * super_rate
        insurance = base * workcover_rate
        thc = base + provisioning + super_cost + insurance
    elif emp_type == "Sponsored":
        provisioning = base * provision_rate
        super_cost = base * super_rate
        insurance = base * workcover_rate
        visa_cost = worker["sponsorship_monthly"] / monthly_hours
        thc = base + provisioning + super_cost + insurance + visa_cost
        
    return thc

# --- Sidebar: Worker Profiles & Settings ---
st.sidebar.title("👷 Configuration")

api_key = st.sidebar.text_input("Gemini API Key (Required for Drop Zone)", type="password")
if api_key:
    genai.configure(api_key=api_key)

st.sidebar.header("Worker Profiles")
for i, worker in enumerate(st.session_state.workers):
    with st.sidebar.expander(worker["name"], expanded=False):
        worker["name"] = st.text_input("Name", value=worker["name"], key=f"name_{i}")
        worker["type"] = st.selectbox(
            "Employment Type", 
            ["ABN", "TFN Full-Time", "TFN Casual", "Sponsored"], 
            index=["ABN", "TFN Full-Time", "TFN Casual", "Sponsored"].index(worker["type"]), 
            key=f"type_{i}"
        )
        worker["base_rate"] = st.number_input("Base Rate ($/hr)", value=worker["base_rate"], min_value=0.0, step=1.0, key=f"base_rate_{i}")
        if worker["type"] == "Sponsored":
            worker["sponsorship_monthly"] = st.number_input("Monthly Visa Overhead ($)", value=worker["sponsorship_monthly"], min_value=0.0, step=100.0, key=f"visa_{i}")
        worker["charge_rate"] = st.number_input("Specific Offsite Charge ($/hr)", value=worker["charge_rate"], min_value=0.0, step=1.0, key=f"charge_{i}")
        
        col_hp, col_hb = st.columns(2)
        worker["hours_paid"] = col_hp.number_input("Hrs Paid", value=worker.get("hours_paid", 40.0), key=f"hp_{i}")
        worker["hours_billed"] = col_hb.number_input("Hrs Billed", value=worker.get("hours_billed", 35.0), key=f"hb_{i}")
        
        thc = calculate_thc(worker)
        st.write(f"**Loaded Cost (THC):** <span class='orange-text'>${thc:.2f}/hr</span>", unsafe_allow_html=True)

# Main Application Tabs
tab1, tab2 = st.tabs(["📊 Dashboard & Sweet Spot", "📁 Document Intelligence (Drop Zone)"])

with tab1:
    st.header("🧮 1. Individual Margin Table")
    data = []
    for worker in st.session_state.workers:
        thc = calculate_thc(worker)
        net_margin = worker["charge_rate"] - thc
        data.append({
            "Worker Name": worker["name"],
            "Employment Type": worker["type"],
            "Loaded Cost (THC)": f"${thc:.2f}/hr",
            "Offsite Charge Rate": f"${worker['charge_rate']:.2f}/hr",
            "Net Margin": f"${net_margin:.2f}/hr"
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)

    st.divider()

    st.header("🎯 2. The \"Sweet Spot\" Profit Engine")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("### Adjust Global Charge Rate")
        global_charge_rate = st.slider("Target 'Sweet Spot' Charge Rate ($/hr)", min_value=60.0, max_value=150.0, value=90.0, step=1.0)
        st.markdown("### FY Visualization Context")
        gst_toggle = st.radio("Financial View", ["Gross Cashflow (Inc GST)", "Net Profit (Ex-GST)"])

    with col2:
        FY_HOURS = 1824 # ~152 hrs * 12 months
        total_fy_profit = sum((global_charge_rate - calculate_thc(w)) * FY_HOURS for w in st.session_state.workers)
        total_fy_revenue = global_charge_rate * FY_HOURS * len(st.session_state.workers)
        
        display_profit = total_fy_profit * 1.10 if "Inc GST" in gst_toggle else total_fy_profit
        display_revenue = total_fy_revenue * 1.10 if "Inc GST" in gst_toggle else total_fy_revenue
        gst_label = "INC GST" if "Inc GST" in gst_toggle else "EX GST"

        st.markdown(f"""
        <div class="metric-card">
            <h3>Total FY Net Profit Projection</h3>
            <h1><span class="green-text">${display_profit:,.2f}</span> <small style="font-size:0.4em;">{gst_label}</small></h1>
            <p>Across all 8 workers @ ${global_charge_rate}/hr (assuming {FY_HOURS} hrs/yr each).</p>
            <hr style="border-color: #555;">
            <p><b>Total FY Revenue:</b> ${display_revenue:,.2f} {gst_label}</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    st.header("⏱️ 3. Billing Efficiency & Burn Rate")
    eff_col, burn_col = st.columns([1, 1])
    with eff_col:
        st.markdown("### Billing Efficiency (Weekly Gap)")
        eff_data = []
        for worker in st.session_state.workers:
            hp = worker.get("hours_paid", 40.0)
            hb = worker.get("hours_billed", 35.0)
            gap = hp - hb
            gap_percent = (gap / hp * 100) if hp > 0 else 0
            eff_data.append({
                "Worker": worker["name"], "Paid Hrs": hp, "Billed Hrs": hb, 
                "Gap %": f"{gap_percent:.1f}%", "Status": "🔴 GAP > 10%" if gap_percent > 10 else "🟢 OK"
            })
        
        df_eff = pd.DataFrame(eff_data)
        def highlight_gap(row):
            return ['background-color: #550000; color: white' if 'GAP > 10%' in row['Status'] else '' for _ in row]
        st.dataframe(df_eff.style.apply(highlight_gap, axis=1), use_container_width=True)

    with burn_col:
        st.markdown("### Monthly Fixed Overheads (Burn Rate FY25/26)")
        burn_data = pd.DataFrame({
            "Month": ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "Fuel": [1200, 1250, 1100, 1400, 1300, 1000, 950, 1150, 1300, 1280, 1450, 1500],
            "Insurance": [200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200],
            "Visa Fees": [1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500],
            "Apps/Software": [150, 150, 150, 150, 150, 150, 150, 150, 150, 150, 150, 150]
        })
        fig = px.line(burn_data, x="Month", y=["Fuel", "Insurance", "Visa Fees", "Apps/Software"], 
                      title="Burn Rate Breakdown", color_discrete_sequence=['#FF5F15', '#39FF14', '#00BFFF', '#FFD700'])
        fig.update_layout(plot_bgcolor='#2A2A2A', paper_bgcolor='#2A2A2A', font_color='#E0E0E0', 
                          legend_title_text='Expense Category', margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("🗂️ Document drop zone (In & Out Pipeline)")
    
    # File Uploader
    uploaded_files = st.file_uploader("Upload CSV, PDF, or Images (Receipts/Invoices)", 
                                      type=['csv', 'pdf', 'png', 'jpeg', 'jpg'], accept_multiple_files=True)
    
    if st.button("Process Documents", type="primary"):
        if not uploaded_files:
            st.warning("Please upload some files first.")
        else:
            with st.spinner("Processing documents with Smart Tagging & AI Vision..."):
                for file in uploaded_files:
                    # CSV processing logic
                    if file.name.lower().endswith(".csv"):
                        try:
                            df_csv = pd.read_csv(file)
                            for _, row in df_csv.iterrows():
                                # Try to grab realistic columns or fallback to index
                                cols = df_csv.columns
                                date_col = next((c for c in cols if 'date' in c.lower()), cols[0])
                                desc_col = next((c for c in cols if 'desc' in c.lower() or 'detail' in c.lower() or 'vendor' in c.lower()), cols[1] if len(cols)>1 else cols[0])
                                amt_col = next((c for c in cols if 'amount' in c.lower() or 'total' in c.lower()), cols[2] if len(cols)>2 else cols[0])
                                
                                desc = str(row.get(desc_col, "")).upper()
                                amt = row.get(amt_col, 0.0)
                                date = str(row.get(date_col, ""))
                                
                                category = "Other"
                                linked_worker = None
                                if any(x in desc for x in ["AMPOL", "BP", "SHELL"]):
                                    category = "Fuel"
                                elif any(x in desc for x in ["BUNNINGS", "TOTAL TOOLS", "PASLODE"]):
                                    category = "Consumables"
                                elif "OFFSITE" in desc:
                                    category = "Income"
                                
                                # Check for worker name matching
                                for w in st.session_state.workers:
                                    if w["name"].upper() in desc:
                                        linked_worker = w["name"]
                                        if category == "Income":
                                            # Revenue mapped to worker
                                            pass
                                        else:
                                            category = "Labor Cost"
                                        break
                                
                                if "ABN" in desc and category == "Other":
                                    category = "Labor Cost"
                                
                                st.session_state.transactions.append({
                                    "Date": date, "Vendor/Desc": desc, "Amount": amt, "GST": abs(float(amt)) / 11 if category in ["Consumables", "Fuel"] else 0,
                                    "Category": category, "Linked": linked_worker, "Confidence": 100, "Source": file.name, "Status": "Auto-Approved"
                                })
                        except Exception as e:
                            st.error(f"Failed to process CSV {file.name}: {e}")
                    
                    # PDF / Image processing logic using Gemini
                    elif file.name.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
                        if not api_key:
                            st.error("Please provide a Gemini API Key in the sidebar to process PDFs/Images.")
                            continue
                        
                        try:
                            # Extract image
                            images = []
                            if file.name.lower().endswith(".pdf"):
                                doc = fitz.open(stream=file.read(), filetype="pdf")
                                # Read first page only for now
                                page = doc[0]
                                pix = page.get_pixmap()
                                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                                images.append(img)
                            else:
                                images.append(Image.open(file))
                            
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            prompt = '''
                            You are a financial receipt/invoice analyzer for an Australian carpentry business.
                            Extract the following details from the uploaded document:
                            - Date (YYYY-MM-DD format if possible)
                            - Vendor (Name of the store, company, or person)
                            - Total Amount (numeric value only without $ sign)
                            - GST (numeric value only, assume 1/11th of total approx if it says "Includes GST". If explicit, use that.)
                            - Reference (Job Name or Subbie Name if available. Look for "Offsite" as a job name.)
                            - Confidence (A score from 0-100 indicating how confident you are in this extraction. E.g., 90 if blurry or missing details).
                            
                            Return the result ONLY as raw JSON formatted exactly like this without markdown backticks:
                            {"Date": "2026-03-24", "Vendor": "Bunnings", "Total Amount": 150.00, "GST": 13.63, "Reference": "Offsite Job", "Confidence": 98}
                            '''
                            
                            response = model.generate_content([prompt, images[0]])
                            clean_text = response.text.replace("```json", "").replace("```", "").strip()
                            data = json.loads(clean_text)
                            
                            desc = (str(data.get("Vendor", "")) + " " + str(data.get("Reference", ""))).upper()
                            
                            category = "Other"
                            linked_worker = None
                            
                            if any(x in desc for x in ["AMPOL", "BP", "SHELL"]):
                                category = "Fuel"
                            elif any(x in desc for x in ["BUNNINGS", "TOTAL TOOLS", "PASLODE"]):
                                category = "Consumables"
                            elif "OFFSITE" in desc:
                                category = "Income"
                                
                            for w in st.session_state.workers:
                                if w["name"].upper() in desc:
                                    linked_worker = w["name"]
                                    if category != "Income":
                                        category = "Labor Cost"
                                    break
                                    
                            if "ABN" in desc and category == "Other":
                                category = "Labor Cost"
                                
                            confidence = int(data.get("Confidence", 90))
                            
                            txn = {
                                "Date": data.get("Date"), 
                                "Vendor/Desc": data.get("Vendor"), 
                                "Amount": float(data.get("Total Amount", 0)), 
                                "GST": float(data.get("GST", 0)),
                                "Category": category, 
                                "Linked": linked_worker,
                                "Confidence": confidence, 
                                "Source": file.name,
                                "Status": "Queue" if confidence < 95 else "Auto-Approved"
                            }
                            
                            if confidence < 95:
                                st.session_state.review_queue.append(txn)
                            else:
                                st.session_state.transactions.append(txn)
                                
                        except Exception as e:
                            st.error(f"Failed to process {file.name} with AI: {e}")
                st.success("File processing complete!")

    # Review Queue UI
    if len(st.session_state.review_queue) > 0:
        st.subheader(f"⚠️ Review Queue ({len(st.session_state.review_queue)} items)")
        st.caption("AI Confidence was under 95%. Please confirm details manually before adding to ledger.")
        
        for idx, q_item in enumerate(st.session_state.review_queue):
            with st.expander(f"Review: {q_item['Source']} ({q_item['Confidence']}% Confirm) - {q_item['Vendor/Desc']} (${q_item['Amount']})", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                q_item["Vendor/Desc"] = c1.text_input("Vendor / Desc", q_item["Vendor/Desc"], key=f"rq_v_{idx}")
                q_item["Amount"] = c2.number_input("Amount", value=float(q_item["Amount"]), key=f"rq_a_{idx}")
                
                cats = ["Income", "Fuel", "Consumables", "Labor Cost", "Other"]
                def_cat_idx = cats.index(q_item["Category"]) if q_item["Category"] in cats else 4
                q_item["Category"] = c3.selectbox("Category", cats, index=def_cat_idx, key=f"rq_c_{idx}")
                
                if c4.button("Confirm & Approve", key=f"rq_btn_{idx}"):
                    q_item["Status"] = "Manual-Approved"
                    st.session_state.transactions.append(q_item)
                    st.session_state.review_queue.pop(idx)
                    st.rerun()

    # Processed Transactions Ledger
    st.subheader("Ledger (Processed Transactions)")
    if st.session_state.transactions:
        df_txn = pd.DataFrame(st.session_state.transactions)
        # Apply conditional formatting for Income vs Expense
        def color_ledger(row):
            if row['Category'] == 'Income':
                return ['background-color: rgba(57, 255, 20, 0.1)'] * len(row)
            return [''] * len(row)
            
        st.dataframe(df_txn.style.apply(color_ledger, axis=1), use_container_width=True)
    else:
        st.info("Upload documents to start creating the ledger.")
