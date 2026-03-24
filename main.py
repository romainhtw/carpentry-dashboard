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

# Premium Silicon Valley UX CSS Injection
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        --bg-prime: #09090b; /* Zinc 950 */
        --bg-sec: #18181b;   /* Zinc 900 */
        --border: #27272a;   /* Zinc 800 */
        --brand-accent: #3b82f6; /* Modern Blue */
        --profit-accent: #10b981; /* Emerald Green */
        --text-main: #fafafa;
        --text-muted: #a1a1aa;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }

    /* Hide standard header/footer for clean app feel */
    header[data-testid="stHeader"] { visibility: hidden; }
    footer { visibility: hidden; }

    /* Custom SV-Style Metric Cards */
    .sv-card {
        background-color: var(--bg-sec);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        backdrop-filter: blur(10px);
    }

    .sv-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.4);
        border-color: #3f3f46;
    }

    .sv-title {
        color: var(--text-muted);
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }

    .sv-value {
        font-size: 2.8rem;
        font-weight: 700;
        line-height: 1.1;
        margin: 0;
    }

    .sv-value.green {
        color: var(--profit-accent);
    }

    .sv-value.orange {
        color: var(--brand-accent);
    }
    
    .sv-value.white {
        color: var(--text-main);
    }

    .sv-subtext {
        color: var(--text-muted);
        font-size: 0.9rem;
        margin-top: 12px;
        font-weight: 400;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: var(--bg-prime);
        border-right: 1px solid var(--border);
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        font-weight: 600 !important;
        color: var(--text-main) !important;
    }
    
    /* Headers */
    h1, h2, h3 {
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }
    
    h1 {
        color: var(--text-main) !important;
        margin-bottom: 1.5rem !important;
    }
    
    /* Divider */
    hr {
        border-color: var(--border);
        margin: 2.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Carpentry Precision Engine")
st.markdown("<p style='color: #8b949e; margin-top: -15px; font-size: 1.1rem; margin-bottom: 30px;'>Enterprise-grade financial intelligence for Australian construction.</p>", unsafe_allow_html=True)

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

# --- Sidebar: Configuration ---
st.sidebar.markdown("### ⚙️ System Configuration")

api_key = st.sidebar.text_input("Gemini API Key", type="password", help="Required for Document Intelligence OCR.")
if api_key:
    genai.configure(api_key=api_key)

st.sidebar.markdown("<br>### 👷 Worker Profiles", unsafe_allow_html=True)
for i, worker in enumerate(st.session_state.workers):
    with st.sidebar.expander(worker["name"], expanded=False):
        worker["name"] = st.text_input("Name", value=worker["name"], key=f"name_{i}")
        worker["type"] = st.selectbox(
            "Contract Type", 
            ["ABN", "TFN Full-Time", "TFN Casual", "Sponsored"], 
            index=["ABN", "TFN Full-Time", "TFN Casual", "Sponsored"].index(worker["type"]), 
            key=f"type_{i}"
        )
        worker["base_rate"] = st.number_input("Base Rate ($/hr)", value=worker["base_rate"], min_value=0.0, step=1.0, key=f"base_rate_{i}")
        if worker["type"] == "Sponsored":
            worker["sponsorship_monthly"] = st.number_input("Monthly Visa Overhead ($)", value=worker["sponsorship_monthly"], min_value=0.0, step=100.0, key=f"visa_{i}")
        worker["charge_rate"] = st.number_input("Offsite Charge ($/hr)", value=worker["charge_rate"], min_value=0.0, step=1.0, key=f"charge_{i}")
        
        c_hp, c_hb = st.columns(2)
        worker["hours_paid"] = c_hp.number_input("Hrs Paid", value=worker.get("hours_paid", 40.0), key=f"hp_{i}")
        worker["hours_billed"] = c_hb.number_input("Hrs Billed", value=worker.get("hours_billed", 35.0), key=f"hb_{i}")
        
        thc = calculate_thc(worker)
        st.markdown(f"<div style='background:#18181b; padding:10px; border-radius:8px; text-align:center; border:1px solid #27272a; margin-top:10px;'>True Hourly Cost (THC)<br><span style='color:#3b82f6; font-size:1.4rem; font-weight:700;'>${thc:.2f}/hr</span></div>", unsafe_allow_html=True)

# Main Application Tabs
tab1, tab2 = st.tabs(["📊 Analytics Engine", "📁 Intelligence Pipeline"])

with tab1:
    
    # --- Top Metrics Row ---
    FY_HOURS = 1824 # ~152 hrs * 12 months
    
    st.markdown("### The Sweet Spot Margin Estimator")
    
    slider_col, toggle_col = st.columns([3, 1])
    with slider_col:
        global_charge_rate = st.slider("Global Target Charge Rate ($/hr)", min_value=60.0, max_value=150.0, value=90.0, step=1.0)
    with toggle_col:
        gst_toggle = st.radio("Accounting View", ["Gross (Inc GST)", "Net (Ex-GST)"], horizontal=True)

    # Calculate Totals
    total_fy_profit = sum((global_charge_rate - calculate_thc(w)) * FY_HOURS for w in st.session_state.workers)
    total_fy_revenue = global_charge_rate * FY_HOURS * len(st.session_state.workers)
    
    display_profit = total_fy_profit * 1.10 if "Inc" in gst_toggle else total_fy_profit
    display_revenue = total_fy_revenue * 1.10 if "Inc" in gst_toggle else total_fy_revenue
    gst_label = "INC GST" if "Inc" in gst_toggle else "EX GST"

    m1, m2, m3 = st.columns(3)
    
    with m1:
        st.markdown(f"""
        <div class="sv-card">
            <div class="sv-title">Projected FY Net Profit</div>
            <div class="sv-value green">${display_profit:,.0f}</div>
            <div class="sv-subtext">Based on {FY_HOURS} hours/yr • {gst_label}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with m2:
        st.markdown(f"""
        <div class="sv-card">
            <div class="sv-title">Projected FY Revenue</div>
            <div class="sv-value orange">${display_revenue:,.0f}</div>
            <div class="sv-subtext">Cumulative across {len(st.session_state.workers)} workers • {gst_label}</div>
        </div>
        """, unsafe_allow_html=True)

    with m3:
        avg_margin = (sum((global_charge_rate - calculate_thc(w)) for w in st.session_state.workers) / len(st.session_state.workers)) if st.session_state.workers else 0
        st.markdown(f"""
        <div class="sv-card">
            <div class="sv-title">Average Hourly Margin</div>
            <div class="sv-value white">${avg_margin:,.2f}</div>
            <div class="sv-subtext">Average net profit created per man-hour</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- Margin Table styling ---
    st.markdown("### Individual Workforce Margins")
    data = []
    for worker in st.session_state.workers:
        thc = calculate_thc(worker)
        net_margin = worker["charge_rate"] - thc
        data.append({
            "Worker Name": worker["name"],
            "Contract": worker["type"],
            "True Cost (THC)": f"${thc:.2f}/hr",
            "Charge Rate": f"${worker['charge_rate']:.2f}/hr",
            "Net Margin": f"${net_margin:.2f}/hr"
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # --- Efficiency & Burn Rate ---
    eff_col, burn_col = st.columns([1, 1], gap="large")
    with eff_col:
        st.markdown("### Billing Efficiency Check")
        st.markdown("<p style='color:var(--text-muted); font-size:0.9rem;'>Highlighting disparities between hours paid and billed offsite.</p>", unsafe_allow_html=True)
        eff_data = []
        for worker in st.session_state.workers:
            hp = worker.get("hours_paid", 40.0)
            hb = worker.get("hours_billed", 35.0)
            gap = hp - hb
            gap_percent = (gap / hp * 100) if hp > 0 else 0
            eff_data.append({
                "Worker": worker["name"], "Paid": hp, "Billed": hb, 
                "Gap %": f"{gap_percent:.1f}%", "Status": "Critical Leak > 10%" if gap_percent > 10 else "Healthy"
            })
        
        df_eff = pd.DataFrame(eff_data)
        def highlight_gap(row):
            return ['background-color: rgba(255, 51, 51, 0.15); color: #FF6B6B;' if 'Critical' in row['Status'] else '' for _ in row]
        st.dataframe(df_eff.style.apply(highlight_gap, axis=1), use_container_width=True, hide_index=True)

    with burn_col:
        st.markdown("### Organizational Burn Rate")
        st.markdown("<p style='color:var(--text-muted); font-size:0.9rem;'>Fixed monthly overhead trajectory (FY25/26).</p>", unsafe_allow_html=True)
        burn_data = pd.DataFrame({
            "Month": ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "Fuel": [1200, 1250, 1100, 1400, 1300, 1000, 950, 1150, 1300, 1280, 1450, 1500],
            "Insurance": [200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200],
            "Visa Fees": [1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500],
            "Apps": [150, 150, 150, 150, 150, 150, 150, 150, 150, 150, 150, 150]
        })
        fig = px.area(burn_data, x="Month", y=["Apps", "Insurance", "Fuel", "Visa Fees"], 
                      color_discrete_sequence=['#52525b', '#71717a', '#a1a1aa', '#3b82f6'])
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)', 
            font_color='#E0E0E0', 
            legend_title_text='', 
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor='#27272a')
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

with tab2:
    st.markdown("### Document Intelligence Pipeline")
    st.markdown("<p style='color:var(--text-muted); font-size:0.95rem; margin-bottom: 20px;'>Drop receipts, bank CSVs, or vendor PDFs. The AI Vision backend will OCR, extract, and categorize them automatically.</p>", unsafe_allow_html=True)
    
    # Drag and Drop Box
    uploaded_files = st.file_uploader("", type=['csv', 'pdf', 'png', 'jpeg', 'jpg'], accept_multiple_files=True)
    
    if st.button("Initialize Pipeline", type="primary", use_container_width=True):
        if not uploaded_files:
            st.warning("Awaiting document upload.")
        else:
            with st.spinner("Neural extraction in progress..."):
                for file in uploaded_files:
                    # CSV processing
                    if file.name.lower().endswith(".csv"):
                        try:
                            df_csv = pd.read_csv(file)
                            for _, row in df_csv.iterrows():
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
                                
                                for w in st.session_state.workers:
                                    if w["name"].upper() in desc:
                                        linked_worker = w["name"]
                                        if category != "Income": category = "Labor Cost"
                                        break
                                
                                if "ABN" in desc and category == "Other":
                                    category = "Labor Cost"
                                
                                st.session_state.transactions.append({
                                    "Date": date, "Vendor": desc, "Amount": amt, "GST": abs(float(amt)) / 11 if category in ["Consumables", "Fuel"] else 0,
                                    "Category": category, "Allocated To": linked_worker, "Confidence": "100%", "Source": file.name, "Status": "Confirmed"
                                })
                        except Exception as e:
                            st.error(f"Failed CSV parse {file.name}: {e}")
                    
                    # PDF / Image processing
                    elif file.name.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
                        if not api_key:
                            st.error("API Key required. Please configure in the system sidebar.")
                            continue
                        
                        try:
                            images = []
                            if file.name.lower().endswith(".pdf"):
                                doc = fitz.open(stream=file.read(), filetype="pdf")
                                page = doc[0]
                                pix = page.get_pixmap()
                                images.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
                            else:
                                images.append(Image.open(file))
                            
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            prompt = '''
                            You are a financial receipt/invoice analyzer for an Australian carpentry business.
                            Extract details strictly into JSON without markdown backticks:
                            {"Date": "YYYY-MM-DD", "Vendor": "Store/Company Name", "Total Amount": 0.00, "GST": 0.00, "Reference": "Job Name", "Confidence": 98}
                            '''
                            
                            response = model.generate_content([prompt, images[0]])
                            clean_text = response.text.replace("```json", "").replace("```", "").strip()
                            data = json.loads(clean_text)
                            
                            desc = (str(data.get("Vendor", "")) + " " + str(data.get("Reference", ""))).upper()
                            
                            category = "Other"
                            linked_worker = None
                            
                            if any(x in desc for x in ["AMPOL", "BP", "SHELL"]): category = "Fuel"
                            elif any(x in desc for x in ["BUNNINGS", "TOTAL TOOLS", "PASLODE"]): category = "Consumables"
                            elif "OFFSITE" in desc: category = "Income"
                                
                            for w in st.session_state.workers:
                                if w["name"].upper() in desc:
                                    linked_worker = w["name"]
                                    if category != "Income": category = "Labor Cost"
                                    break
                                    
                            if "ABN" in desc and category == "Other": category = "Labor Cost"
                                
                            confidence = int(data.get("Confidence", 90))
                            
                            txn = {
                                "Date": data.get("Date"), 
                                "Vendor": data.get("Vendor", desc), 
                                "Amount": float(data.get("Total Amount", 0)), 
                                "GST": float(data.get("GST", 0)),
                                "Category": category, 
                                "Allocated To": linked_worker,
                                "Confidence": f"{confidence}%", 
                                "Source": file.name,
                                "Status": "Awaiting Review" if confidence < 95 else "Confirmed"
                            }
                            
                            if confidence < 95:
                                st.session_state.review_queue.append(txn)
                            else:
                                st.session_state.transactions.append(txn)
                                
                        except Exception as e:
                            st.error(f"Vision failure on {file.name}: {e}")
                st.success("Extraction Complete.")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Review Queue UI
    if len(st.session_state.review_queue) > 0:
        st.markdown(f"### ⚠️ Action Required: Human Validation ({len(st.session_state.review_queue)})")
        st.markdown("<p style='color:var(--text-muted); font-size:0.9rem;'>The vision model reported <95% probability on these items.</p>", unsafe_allow_html=True)
        
        for idx, q_item in enumerate(st.session_state.review_queue):
            with st.expander(f"Anomaly: {q_item['Source']} ({q_item['Confidence']} Confidence) — {q_item['Vendor']} (${q_item['Amount']})", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                q_item["Vendor"] = c1.text_input("Entity", q_item["Vendor"], key=f"rq_v_{idx}")
                q_item["Amount"] = c2.number_input("Extracted ($)", value=float(q_item["Amount"]), key=f"rq_a_{idx}")
                
                cats = ["Income", "Fuel", "Consumables", "Labor Cost", "Other"]
                def_cat_idx = cats.index(q_item["Category"]) if q_item["Category"] in cats else 4
                q_item["Category"] = c3.selectbox("Routing Rule", cats, index=def_cat_idx, key=f"rq_c_{idx}")
                
                st.markdown("<br>", unsafe_allow_html=True)
                if c4.button("Verify & Commit", key=f"rq_btn_{idx}", use_container_width=True):
                    q_item["Status"] = "Confirmed"
                    st.session_state.transactions.append(q_item)
                    st.session_state.review_queue.pop(idx)
                    st.rerun()

    # Processed Transactions Ledger
    st.markdown("### Transaction Ledger")
    st.markdown("<p style='color:var(--text-muted); font-size:0.9rem;'>Immutable record of system-verified ingestions.</p>", unsafe_allow_html=True)
    if st.session_state.transactions:
        df_txn = pd.DataFrame(st.session_state.transactions)
        def color_ledger(row):
            if row['Category'] == 'Income': return ['background-color: rgba(57, 255, 20, 0.05); color: #39FF14'] * len(row)
            return [''] * len(row)
            
        st.dataframe(df_txn.style.apply(color_ledger, axis=1), use_container_width=True, hide_index=True)
    else:
        st.markdown("""
        <div style="padding: 40px; text-align: center; border: 1px dashed #30363d; border-radius: 12px; color: #8b949e;">
            <div style="font-size: 2rem; margin-bottom: 10px;">📉</div>
            No transactions verified. Database is empty.
        </div>
        """, unsafe_allow_html=True)
