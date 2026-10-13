# El-Sharnouby Enterprise Analytics

**An Integrated Business Intelligence & Analytics Platform**

## Overview

El-Sharnouby Enterprise Analytics is a business analytics project built with Python, Dash, Pandas, and Plotly. It consists of seven interactive analytical applications designed to transform business data into actionable insights and support data-driven decision-making across key business functions.

The platform covers executive reporting, inventory management, customer analytics, production control, marketing performance, branch expansion, and procurement risk.

## Business Objectives

- Provide executive-level visibility into business performance.
- Improve inventory availability and replenishment decisions.
- Understand customer behavior and retention opportunities.
- Monitor production performance and operational efficiency.
- Evaluate marketing performance and growth opportunities.
- Compare branch performance and support expansion decisions.
- Analyze procurement costs and supplier-related risks.

## The Seven Applications

### 01. Executive Command Center

**Focus:** Executive reporting and business performance.

Provides a high-level overview of business performance through key performance indicators (KPIs), helping executives monitor results and identify areas requiring attention.

Key analytical areas:
- Net Sales and Gross Profit
- Gross Margin
- Product and Customer Performance
- Production Efficiency
- Current Inventory Levels

**Business Value:** Supports strategic planning and executive decision-making through a consolidated view of key business metrics.

### 02. Smart Inventory & Replenishment

**Focus:** Inventory optimization and replenishment planning.

Analyzes inventory positions across products and locations to identify stock risks and potential replenishment actions.

Key analytical areas:
- Current Stock Levels
- Inventory at Risk
- Days of Inventory Coverage
- Stockout Risk
- External Replenishment Requirements
- Suggested Internal Inventory Transfers

**Business Value:** Helps determine what inventory needs attention, where stock should be moved, and where additional replenishment may be required.

### 03. Customer 360 & Retention

**Focus:** Customer analytics and retention.

Brings customer-related analysis together to support a better understanding of customer performance and retention opportunities.

Key analytical areas:
- Customer Performance
- Customer Segmentation
- Purchasing Behavior
- Retention Opportunities
- Identification of Customers Requiring Attention

**Business Value:** Helps identify valuable customer segments and opportunities to strengthen customer relationships and retention.

### 04. Factory Digital Twin & Production Control

**Focus:** Production monitoring and operational efficiency.

Analyzes production-related information to help monitor operational performance and identify potential production issues.

Key analytical areas:
- Production Order Performance
- Production Efficiency
- Production Status Monitoring
- Operational Bottlenecks
- Production Performance Comparisons

**Business Value:** Supports production planning, performance monitoring, and the identification of opportunities to improve operational efficiency.

### 05. Marketing Attribution & Growth Analytics

**Focus:** Marketing performance and business growth.

Examines marketing-related data to help assess campaign performance and understand how marketing activities contribute to business outcomes.

Key analytical areas:
- Marketing Campaign Performance
- Marketing Channel Analysis
- Campaign Effectiveness
- Growth Opportunities
- Marketing Performance Comparisons

**Business Value:** Helps evaluate marketing initiatives and identify opportunities to improve campaign effectiveness and growth.

### 06. Branch Performance & Expansion Intelligence

**Focus:** Branch performance and expansion planning.

Analyzes business performance across branches or locations to support comparisons and identify potential expansion opportunities.

Key analytical areas:
- Branch Performance
- Location-Based Comparisons
- Sales and Business Trends
- Underperforming Locations
- Potential Expansion Opportunities

**Business Value:** Supports location-level performance assessment and more informed decisions about business expansion.

### 07. Procurement, Cost & Supplier Risk

**Focus:** Procurement analytics, cost management, and supplier risk.

Analyzes procurement and supplier-related information to identify cost patterns, delivery concerns, and potential operational risks.

Key analytical areas:
- Procurement Spending
- Purchase Order Analysis
- Supplier Performance
- Supplier Delays and Risk
- Material Unit Costs
- Quality-Related Losses

**Business Value:** Helps improve procurement visibility, evaluate supplier reliability, monitor costs, and identify potential supply-chain risks.

## Data Understanding & Quality Assessment

The project also includes `understand_data.ipynb`, a Jupyter Notebook for exploring the available datasets and understanding their structure before building analytical applications.

Its purpose includes:
- Inspecting columns and data types.
- Reviewing dataset structure and dimensions.
- Identifying missing values.
- Exploring potential data-quality issues.
- Supporting the preparation of data for analysis.

## Technology Stack

- **Python** — Core programming language
- **Pandas** — Data manipulation and analysis
- **Dash** — Interactive web dashboards
- **Plotly** — Interactive charts and visualizations
- **Jupyter Notebook** — Data exploration and understanding

## Project Structure

The repository contains seven Python analytics applications and a data-understanding notebook.

Each application focuses on a distinct business function, while the notebook supports the initial data exploration process.

## Getting Started

pip install -r requirements.txt
python unified_app.py
