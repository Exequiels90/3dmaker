# 3D Printing Workshop Management System

A professional-grade web application for managing a 3D printing workshop with complete cost tracking, inventory management, sales processing, and waste tracking.

## Features

### 📊 Dashboard & Analytics
- **KPI Monitoring**: Real-time display of monthly revenue, net profit, filament stock, and active alerts
- **Revenue vs Costs**: Monthly comparison bar chart showing profitability trends
- **Cost Breakdown**: Interactive pie chart showing cost distribution by component (material, electricity, depreciation, labor, additional)
- **Waste Tracking**: Line chart showing filament waste trends over time

### 💰 Sales & Order Management
- **Dynamic Order Creation**: Add multiple items per order with real-time price suggestions
- **Auto Stock Validation**: Prevents overselling by checking material availability
- **Channel-Based Fees**: Apply platform-specific commissions (Instagram, Web, etc.)
- **Order Tracking**: Monitor orders from pending through delivery with status updates
- **Financial Summaries**: Track gross profit, net profit after fees, and production costs

### 📦 Inventory Management
- **Product Catalog**: Manage designs with weight, print time, labor time specifications
- **Cost Calculation**: Automatically compute production cost based on:
  - Material usage (weight × cost per gram)
  - Electricity consumption (watts × hours × $/kWh)
  - Machine depreciation (hours × depreciation rate)
  - Labor cost (hours × hourly rate)
  - Additional expenses (hardware, packaging, etc.)
- **Dynamic Pricing**: Auto-generate suggested selling prices based on margin percentage
- **Filament Stock**: Visual inventory with color-coded progress bars (green >50%, yellow 15-50%, red <15%)

### 🔧 Infrastructure Management
- **Printer Tracking**: Monitor machine hours, power consumption, depreciation
- **Maintenance Logging**: Record maintenance dates, descriptions, and costs
- **Maintenance Alerts**: Automatic notification when machines require service (every 500+ hours)

### 🚨 Waste & Quality Control
- **Waste Logging**: Record failed prints with reason and weight wasted
- **Financial Impact**: Automatically calculate waste cost impact
- **Stock Deduction**: Immediate inventory reduction on waste registration

### ⚙️ System Configuration
- **Global Settings**:
  - Electricity rate ($ per kWh)
  - Labor rate ($ per hour)
  - Base profit margin (%)
  - Failure risk multiplier
- **Supplier Management**: Track material suppliers and contact information
- **Maintenance History**: View all maintenance records with costs

---

## Architecture

### Database Models

```
Supplier (1) ──→ (∞) Material
Printer (1) ──→ (∞) MaintenanceLog
Material (1) ──→ (∞) WasteLog

Material (1) ──→ (∞) Product
Printer (1) ──→ (∞) Product

Product (1) ──→ (∞) OrderItem
Order (1) ──→ (∞) OrderItem
Customer (1) ──→ (∞) Order

GlobalConfig (Singleton)
```

### Cost Calculation Formula

For each product/order item:

```
Production Cost Per Unit = (
  + (slicer_weight_grams × material.cost_per_gram)
  + ((printer.power_watts / 1000) × print_time_hours × kwh_cost)
  + (print_time_hours × printer.depreciation_per_hour)
  + (post_process_hours × labor_hour_cost)
  + additional_costs
)

Suggested Price = Production Cost × (1 + base_profit_margin / 100)

Order Profit = 
  - Total Revenue
  - Total Production Costs
  - Platform Fees
```

### API Endpoints

#### Dashboard & Analytics
- `GET /api/kpis` - KPI values for dashboard
- `GET /api/chart/revenue-vs-costs` - Monthly revenue vs costs chart data
- `GET /api/chart/waste-trends` - Waste trends over time
- `GET /api/chart/cost-breakdown/<product_id>` - Cost breakdown for a product

#### Sales
- `POST /api/sales/create` - Create new order
- `GET /api/sales/list?status=&channel=&date_from=&date_to=` - List orders with filters
- `POST /api/sales/<order_id>/update-status` - Update order status

#### Products
- `GET /api/products` - List all products
- `GET /api/products/<product_id>` - Get product details
- `POST /api/products/create` - Create new product

#### Inventory
- `GET /api/materials` - List all materials
- `POST /api/materials/create` - Add new material

#### Waste
- `POST /api/waste/log` - Log material waste

#### Printers
- `GET /api/printers` - List all printers
- `POST /api/printers/create` - Add new printer
- `POST /api/maintenance/log` - Log maintenance

#### Configuration
- `POST /api/config/update` - Update global settings

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- Flask 2.0+
- SQLAlchemy 3.0+

### Steps

1. **Clone/Download the project**
   ```bash
   cd so
   ```

2. **Create virtual environment (optional)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the web interface**
   - Open browser to: `http://localhost:5000`

### ⚠️ If you get "no such column: order.customer_id" error:

This happens if an old database exists with incompatible schema. Solution:

```bash
# Step 1: Stop the app (Ctrl+C)

# Step 2: Clean the database
python cleanup_db.py

# Step 3: Restart the app
python app.py
```

Or use the automatic script:
```bash
recreate_db.bat
```

See `SOLUCION_ERROR.md` for detailed troubleshooting.

---

## Project Structure

```
project/
├── app.py                    # Application factory & main entry point
├── models.py                 # SQLAlchemy models (complete data schema)
├── routes.py                 # Flask blueprints & API endpoints
├── requirements.txt          # Python dependencies
├── so.sqlite                 # SQLite database (auto-created)
│
├── templates/
│   ├── layout.html          # Base AdminLTE template
│   ├── dashboard.html       # Dashboard with KPIs & charts
│   ├── sales.html           # Sales & order management
│   ├── inventory.html       # Product & filament inventory
│   ├── config.html          # System configuration
│   └── producto_detalle.html # Legacy product detail view
│
└── venv/                     # Virtual environment
```

---

## Key Features Explained

### Stock Management
When an order is created:
1. System validates available material
2. If insufficient stock → error message shown
3. If sufficient → automatic deduction upon order completion
4. Stock updates immediately in inventory

### Waste Tracking Impact
When waste is logged:
1. Material weight reduced from current_weight
2. Cost impact calculated (weight × cost_per_gram)
3. Reflected in monthly profit calculations
4. Visible in waste trends chart

### Machine Hour Tracking
- Auto-incremented when orders complete
- Depreciation cost calculated per hour
- Maintenance alert triggered at 500+ hours since last service
- Supports multiple printers with individual tracking

### Financial Accuracy
- All costs calculated with 4 decimal precision
- Production costs frozen at order time (snapshot) for audit trail
- Profit calculated after deducting platform fees
- Monthly reports aggregated by customer, channel, and product

---

## Usage Guide

### Creating a Product
1. Go to **Inventory** → **Add New Product**
2. Fill in:
   - Product name
   - Weight (from slicer, including supports)
   - Print time (decimal hours)
   - Post-processing time
   - Default material & printer
   - Any additional costs
3. System auto-calculates production cost & suggested price

### Recording a Sale
1. Go to **Sales & Orders** → **Create New Order**
2. Select/create customer
3. Choose sale channel (affects platform fee)
4. Add items (system shows production cost & suggested price)
5. Adjust final price if needed
6. Submit → Order created, stock deducted, profit calculated

### Logging Waste
1. Go to **Inventory** → **Filament Inventory**
2. Click **Log Waste** on any material
3. Enter grams wasted & reason
4. Cost impact calculated automatically
5. Stock reduced, visible in reports

### Updating Printer Maintenance
1. Go to **Configuration** → **Add Maintenance**
2. Select printer
3. Enter maintenance description & cost
4. System resets maintenance timer
5. Removes alert from dashboard

---

## Configuration Reference

All settings stored in `GlobalConfig` table, editable via `/config` page:

| Setting | Default | Notes |
|---------|---------|-------|
| kwh_cost | 0.12 | Your local electricity rate |
| labor_hour_cost | 15.0 | Your hourly labor cost |
| base_profit_margin | 150.0 | Markup % on production cost |
| fail_margin_multiplier | 1.05 | Risk factor (1.05 = 5% extra) |

---

## Troubleshooting

### "Insufficient stock" error
- Check inventory levels in **Inventory** page
- Verify material current_weight reflects recent adjustments
- Log waste or add new material if needed

### Costs seem incorrect
- Verify config settings (kWh, labor rate, margins)
- Check product specifications (weight, times)
- Ensure printer & material are properly linked

### Charts not loading
- Check browser console for errors
- Verify API endpoints return valid JSON
- Clear browser cache and reload

---

## Performance Notes

- Dashboard KPIs load data from last 12 months
- All calculations use floating-point precision (rounded to 2 decimals for display)
- Database queries optimized with proper indexing on foreign keys
- Real-time updates via AJAX to prevent full page reloads

---

## Future Enhancements

- Multi-user support with role-based access control
- Email/PDF invoice generation
- Advanced filtering & custom reports
- Batch import/export for data migration
- Mobile app version
- Integration with third-party payment gateways
- Predictive maintenance scheduling
- Material supplier price tracking

---

## Support & Documentation

For detailed API documentation, see comments in `routes.py`
For model structure details, see docstrings in `models.py`

---

**Version:** 1.0  
**Last Updated:** 2026-05-29  
**License:** MIT (Customize as needed)
