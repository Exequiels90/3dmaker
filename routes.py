from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for, Response, session
from flask_login import login_user, logout_user, login_required, current_user
from models import (db, Product, Material, Printer, GlobalConfig, Order, OrderItem, 
                    Customer, WasteLog, MaintenanceLog, Supplier, ProductMaterial, Expense, User, CustomerOrder, ProductImage)
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import json

main = Blueprint('main', __name__)


# ==================== LANGUAGE ====================

@main.route('/set_language/<lang>')
def set_language(lang):
    """Cambiar el idioma de la aplicación"""
    if lang in ['es', 'en']:
        session['language'] = lang
    return redirect(request.referrer or url_for('main.dashboard'))


# ==================== DASHBOARD & ANALYTICS ====================

@main.route('/')
def index():
    """Redirigir a setup si no hay usuarios, si no a login"""
    try:
        user_count = User.query.count()
        if user_count == 0:
            return redirect(url_for('main.setup'))
    except:
        # Si hay error en la base de datos, ir a setup
        return redirect(url_for('main.setup'))
    return redirect(url_for('main.dashboard'))


@main.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal con KPIs"""
    # Limpiar órdenes expiradas automáticamente
    cleanup_expired_orders()
    
    config = GlobalConfig.get_singleton()
    
    # Calculate current month boundaries
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    month_end = datetime(now.year, now.month + 1 if now.month < 12 else 1, 1) if now.month < 12 else datetime(now.year + 1, 1, 1)
    
    # KPI 1: Monthly revenue and order count
    month_orders = Order.query.filter(
        Order.date >= month_start,
        Order.date < month_end,
        Order.status != 'Cancelled'
    ).all()
    
    monthly_revenue = sum(o.total_amount_billed or 0.0 for o in month_orders)
    orders_count = len(month_orders)
    
    # KPI 2: Net profit (revenue - production costs - platform fees - expenses)
    monthly_costs = sum(o.total_production_cost for o in month_orders)
    monthly_fees = sum(o.platform_fee_amount for o in month_orders)
    
    # Add expenses from the current month
    month_expenses = Expense.query.filter(
        Expense.date >= month_start,
        Expense.date < month_end
    ).all()
    monthly_expenses_total = sum(e.amount for e in month_expenses)
    
    monthly_profit = monthly_revenue - monthly_costs - monthly_fees - monthly_expenses_total
    
    # KPI 3: Total kg of filament in stock
    total_filament_kg = sum(m.current_weight for m in Material.query.all()) / 1000.0
    
    # KPI 4: Active alerts (low stock + maintenance needed)
    # remaining_percent and needs_maintenance are Python @property, not DB columns,
    # so filtering must happen in Python after fetching all records.
    low_stock_materials = [m for m in Material.query.all() if m.remaining_percent < 15]
    printers_needing_maintenance = [p for p in Printer.query.all() if p.needs_maintenance]
    total_alerts = len(low_stock_materials) + len(printers_needing_maintenance)
    
    # KPI 5: Monthly growth percentage
    last_month_date = now - timedelta(days=30)
    last_month_start = datetime(last_month_date.year, last_month_date.month, 1)
    last_month_end = datetime(now.year, now.month, 1)
    
    last_month_orders = Order.query.filter(
        Order.date >= last_month_start,
        Order.date < last_month_end,
        Order.status != 'Cancelled'
    ).all()
    
    last_month_revenue = sum(o.total_amount_billed or 0.0 for o in last_month_orders)
    
    if last_month_revenue > 0:
        monthly_growth = ((monthly_revenue - last_month_revenue) / last_month_revenue) * 100
    else:
        monthly_growth = 0 if monthly_revenue == 0 else 100
    
    # KPI 6: Average order value
    average_order_value = monthly_revenue / orders_count if orders_count > 0 else 0
    
    context = {
        'monthly_revenue': round(monthly_revenue, 2),
        'orders_count': orders_count,
        'monthly_profit': round(monthly_profit, 2),
        'monthly_expenses': round(monthly_expenses_total, 2),
        'total_filament_kg': round(total_filament_kg, 2),
        'total_alerts': total_alerts,
        'low_stock_count': len(low_stock_materials),
        'maintenance_count': len(printers_needing_maintenance),
        'low_stock_materials': low_stock_materials,
        'monthly_growth': round(monthly_growth, 1),
        'total_orders': orders_count,
        'average_order_value': round(average_order_value, 2),
        'config': config
    }
    
    return render_template('dashboard.html', **context)


@main.route('/api/kpis')
def api_kpis():
    """API endpoint para KPIs del dashboard"""
    config = GlobalConfig.get_singleton()
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    month_end = datetime(now.year, now.month + 1 if now.month < 12 else 1, 1) if now.month < 12 else datetime(now.year + 1, 1, 1)
    
    month_orders = Order.query.filter(
        Order.date >= month_start,
        Order.date < month_end,
        Order.status != 'Cancelled'
    ).all()
    
    monthly_revenue = sum(o.total_amount_billed or 0.0 for o in month_orders)
    monthly_costs = sum(o.total_production_cost for o in month_orders)
    monthly_fees = sum(o.platform_fee_amount for o in month_orders)
    monthly_profit = monthly_revenue - monthly_costs - monthly_fees
    total_filament_kg = sum(m.current_weight for m in Material.query.all()) / 1000.0
    
    return jsonify({
        'monthly_revenue': round(monthly_revenue, 2),
        'orders_count': len(month_orders),
        'monthly_profit': round(monthly_profit, 2),
        'total_filament_kg': round(total_filament_kg, 2),
        'alerts': sum(1 for m in Material.query.all() if m.remaining_percent < 15) + \
                  sum(1 for p in Printer.query.all() if p.needs_maintenance)
    })


@main.route('/api/chart/revenue-vs-costs')
def api_chart_revenue_vs_costs():
    """Gráfico de ingresos vs costos por mes"""
    # Get last 12 months data
    data_by_month = {}
    for i in range(12):
        month_date = datetime.utcnow() - timedelta(days=30 * i)
        month_key = month_date.strftime('%Y-%m')
        if month_key not in data_by_month:
            month_start = datetime(month_date.year, month_date.month, 1)
            month_end = datetime(month_date.year, month_date.month + 1 if month_date.month < 12 else 1, 1) if month_date.month < 12 else datetime(month_date.year + 1, 1, 1)
            
            orders = Order.query.filter(
                Order.date >= month_start,
                Order.date < month_end,
                Order.status != 'Cancelled'
            ).all()
            
            revenue = sum(o.total_amount_billed or 0.0 for o in orders)
            costs = sum(o.total_production_cost for o in orders)
            
            data_by_month[month_key] = {'revenue': revenue, 'costs': costs, 'month': month_date.strftime('%b %y')}
    
    sorted_data = sorted(data_by_month.items())
    labels = [v['month'] for k, v in sorted_data]
    revenues = [v['revenue'] for k, v in sorted_data]
    costs = [v['costs'] for k, v in sorted_data]
    
    return jsonify({
        'labels': labels,
        'datasets': [
            {'label': 'Revenue ($)', 'data': revenues, 'backgroundColor': '#00a65a'},
            {'label': 'Costs ($)', 'data': costs, 'backgroundColor': '#dd4b39'}
        ]
    })


@main.route('/api/chart/cost-breakdown/<int:product_id>')
def api_chart_cost_breakdown(product_id):
    """Desglose de costos de un producto específico"""
    product = Product.query.get_or_404(product_id)
    config = GlobalConfig.get_singleton()
    costs = product.calculate_production_cost(config)
    
    total = costs['total']
    labels = ['Material', 'Electricity', 'Depreciation', 'Labor', 'Additional']
    data = [
        costs['material'],
        costs['electricity'],
        costs['depreciation'],
        costs['labor'],
        costs['additional']
    ]
    
    # Calculate percentages
    percentages = [round(x / total * 100, 1) if total > 0 else 0 for x in data]
    
    return jsonify({
        'labels': labels,
        'data': data,
        'percentages': percentages,
        'total': total
    })


@main.route('/api/chart/waste-trends')
def api_chart_waste_trends():
    """Gráfico de tendencia de desperdicio mensual"""
    data_by_month = {}
    for i in range(12):
        month_date = datetime.utcnow() - timedelta(days=30 * i)
        month_key = month_date.strftime('%Y-%m')
        
        if month_key not in data_by_month:
            month_start = datetime(month_date.year, month_date.month, 1)
            month_end = datetime(month_date.year, month_date.month + 1 if month_date.month < 12 else 1, 1) if month_date.month < 12 else datetime(month_date.year + 1, 1, 1)
            
            waste_logs = WasteLog.query.filter(
                WasteLog.date >= month_start,
                WasteLog.date < month_end
            ).all()
            
            total_waste_grams = sum(w.weight_wasted or 0.0 for w in waste_logs)
            data_by_month[month_key] = {'waste_grams': total_waste_grams, 'month': month_date.strftime('%b %y')}
    
    sorted_data = sorted(data_by_month.items())
    labels = [v['month'] for k, v in sorted_data]
    waste_data = [v['waste_grams'] for k, v in sorted_data]
    
    return jsonify({
        'labels': labels,
        'datasets': [{
            'label': 'Waste (grams)',
            'data': waste_data,
            'borderColor': '#f39c12',
            'backgroundColor': 'rgba(243, 156, 18, 0.1)',
            'fill': True
        }]
    })


@main.route('/api/chart/product-sales')
def api_chart_product_sales():
    """API endpoint para gráfico de ventas por producto"""
    # Get sales by product for the last 12 months
    now = datetime.utcnow()
    twelve_months_ago = now - timedelta(days=365)
    
    # Query all order items in the last 12 months
    order_items = OrderItem.query.join(Order).filter(
        Order.date >= twelve_months_ago,
        Order.status != 'Cancelled'
    ).all()
    
    # Aggregate sales by product
    product_sales = {}
    for item in order_items:
        product_name = item.product.name if item.product else 'Unknown'
        if product_name not in product_sales:
            product_sales[product_name] = {'quantity': 0, 'revenue': 0}
        product_sales[product_name]['quantity'] += item.quantity
        product_sales[product_name]['revenue'] += item.quantity * item.unit_price_sold
    
    # Sort by quantity and take top 10
    sorted_products = sorted(product_sales.items(), key=lambda x: x[1]['quantity'], reverse=True)[:10]
    
    return jsonify({
        'labels': [p[0] for p in sorted_products],
        'quantities': [p[1]['quantity'] for p in sorted_products],
        'revenues': [p[1]['revenue'] for p in sorted_products]
    })


@main.route('/api/chart/sales-by-category')
def api_chart_sales_by_category():
    """API endpoint para gráfico de ventas por categoría"""
    now = datetime.utcnow()
    twelve_months_ago = now - timedelta(days=365)
    
    # Query all order items in the last 12 months
    order_items = OrderItem.query.join(Order).join(Product).filter(
        Order.date >= twelve_months_ago,
        Order.status != 'Cancelled'
    ).all()
    
    # Aggregate sales by category
    category_sales = {}
    for item in order_items:
        category = item.product.category if item.product else 'General'
        if category not in category_sales:
            category_sales[category] = {'quantity': 0, 'revenue': 0}
        category_sales[category]['quantity'] += item.quantity
        category_sales[category]['revenue'] += item.quantity * item.unit_price_sold
    
    return jsonify({
        'labels': list(category_sales.keys()),
        'quantities': [category_sales[cat]['quantity'] for cat in category_sales],
        'revenues': [category_sales[cat]['revenue'] for cat in category_sales]
    })


@main.route('/api/chart/weekly-sales-trends')
def api_chart_weekly_sales_trends():
    """API endpoint para gráfico de tendencias de ventas semanales"""
    now = datetime.utcnow()
    # Get data for the last 12 weeks
    twelve_weeks_ago = now - timedelta(weeks=12)
    
    # Query all orders in the last 12 weeks
    orders = Order.query.filter(
        Order.date >= twelve_weeks_ago,
        Order.status != 'Cancelled'
    ).all()
    
    # Aggregate sales by week
    weekly_sales = {}
    for order in orders:
        # Get the week number (year-week format)
        week_key = order.date.strftime('%Y-W%U')
        if week_key not in weekly_sales:
            weekly_sales[week_key] = {'revenue': 0, 'quantity': 0}
        for item in order.items:
            weekly_sales[week_key]['revenue'] += item.quantity * item.unit_price_sold
            weekly_sales[week_key]['quantity'] += item.quantity
    
    # Sort by week
    sorted_weeks = sorted(weekly_sales.items())
    
    return jsonify({
        'labels': [week[0] for week in sorted_weeks],
        'revenues': [weekly_sales[week[0]]['revenue'] for week in sorted_weeks],
        'quantities': [weekly_sales[week[0]]['quantity'] for week in sorted_weeks]
    })


@main.route('/api/chart/sales-projection')
def api_chart_sales_projection():
    """API endpoint para proyección de ventas basada en datos históricos"""
    now = datetime.utcnow()
    # Get data for the last 6 months for projection
    six_months_ago = now - timedelta(days=180)
    
    # Query all orders in the last 6 months
    orders = Order.query.filter(
        Order.date >= six_months_ago,
        Order.status != 'Cancelled'
    ).all()
    
    # Aggregate sales by month
    monthly_sales = {}
    for order in orders:
        month_key = order.date.strftime('%Y-%m')
        if month_key not in monthly_sales:
            monthly_sales[month_key] = {'revenue': 0, 'quantity': 0}
        for item in order.items:
            monthly_sales[month_key]['revenue'] += item.quantity * item.unit_price_sold
            monthly_sales[month_key]['quantity'] += item.quantity
    
    # Sort by month
    sorted_months = sorted(monthly_sales.items())
    
    # Calculate average monthly revenue for projection
    if len(sorted_months) > 0:
        avg_monthly_revenue = sum(month[1]['revenue'] for month in sorted_months) / len(sorted_months)
        avg_monthly_quantity = sum(month[1]['quantity'] for month in sorted_months) / len(sorted_months)
    else:
        avg_monthly_revenue = 0
        avg_monthly_quantity = 0
    
    # Project next 3 months
    projection_months = []
    projection_revenues = []
    projection_quantities = []
    
    for i in range(1, 4):
        future_date = now + timedelta(days=30 * i)
        future_month = future_date.strftime('%Y-%m')
        projection_months.append(future_month)
        projection_revenues.append(avg_monthly_revenue)
        projection_quantities.append(avg_monthly_quantity)
    
    return jsonify({
        'historical_labels': [month[0] for month in sorted_months],
        'historical_revenues': [monthly_sales[month[0]]['revenue'] for month in sorted_months],
        'historical_quantities': [monthly_sales[month[0]]['quantity'] for month in sorted_months],
        'projection_labels': projection_months,
        'projection_revenues': projection_revenues,
        'projection_quantities': projection_quantities,
        'average_monthly_revenue': avg_monthly_revenue
    })


@main.route('/api/chart/year-over-year')
def api_chart_year_over_year():
    """API endpoint para comparación año vs año"""
    now = datetime.utcnow()
    current_year = now.year
    last_year = current_year - 1
    
    # Get data for current year
    current_year_orders = Order.query.filter(
        Order.date >= datetime(current_year, 1, 1),
        Order.date <= datetime(current_year, 12, 31),
        Order.status != 'Cancelled'
    ).all()
    
    # Get data for last year
    last_year_orders = Order.query.filter(
        Order.date >= datetime(last_year, 1, 1),
        Order.date <= datetime(last_year, 12, 31),
        Order.status != 'Cancelled'
    ).all()
    
    # Aggregate by month for current year
    current_year_monthly = {}
    for order in current_year_orders:
        month_key = order.date.strftime('%m')
        if month_key not in current_year_monthly:
            current_year_monthly[month_key] = {'revenue': 0, 'quantity': 0}
        for item in order.items:
            current_year_monthly[month_key]['revenue'] += item.quantity * item.unit_price_sold
            current_year_monthly[month_key]['quantity'] += item.quantity
    
    # Aggregate by month for last year
    last_year_monthly = {}
    for order in last_year_orders:
        month_key = order.date.strftime('%m')
        if month_key not in last_year_monthly:
            last_year_monthly[month_key] = {'revenue': 0, 'quantity': 0}
        for item in order.items:
            last_year_monthly[month_key]['revenue'] += item.quantity * item.unit_price_sold
            last_year_monthly[month_key]['quantity'] += item.quantity
    
    # Create arrays for all months (1-12)
    months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
    month_names = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    
    current_year_data = [current_year_monthly.get(m, {'revenue': 0})['revenue'] for m in months]
    last_year_data = [last_year_monthly.get(m, {'revenue': 0})['revenue'] for m in months]
    
    # Calculate growth percentage
    growth_data = []
    for i in range(12):
        if last_year_data[i] > 0:
            growth = ((current_year_data[i] - last_year_data[i]) / last_year_data[i]) * 100
        else:
            growth = 0 if current_year_data[i] == 0 else 100
        growth_data.append(growth)
    
    return jsonify({
        'months': month_names,
        'current_year': current_year_data,
        'last_year': last_year_data,
        'growth': growth_data,
        'current_year_total': sum(current_year_data),
        'last_year_total': sum(last_year_data)
    })


@main.route('/api/chart/monthly-growth')
def api_chart_monthly_growth():
    """API endpoint para análisis de crecimiento mensual"""
    now = datetime.utcnow()
    current_month = now.strftime('%Y-%m')
    last_month = (now - timedelta(days=30)).strftime('%Y-%m')
    
    # Get data for current month
    current_month_orders = Order.query.filter(
        Order.date >= datetime(now.year, now.month, 1),
        Order.status != 'Cancelled'
    ).all()
    
    # Get data for last month
    last_month_date = now - timedelta(days=30)
    last_month_orders = Order.query.filter(
        Order.date >= datetime(last_month_date.year, last_month_date.month, 1),
        Order.date < datetime(now.year, now.month, 1),
        Order.status != 'Cancelled'
    ).all()
    
    # Calculate current month revenue
    current_month_revenue = sum(
        item.quantity * item.unit_price_sold
        for order in current_month_orders
        for item in order.items
    )
    
    # Calculate last month revenue
    last_month_revenue = sum(
        item.quantity * item.unit_price_sold
        for order in last_month_orders
        for item in order.items
    )
    
    # Calculate growth percentage
    if last_month_revenue > 0:
        growth_percentage = ((current_month_revenue - last_month_revenue) / last_month_revenue) * 100
    else:
        growth_percentage = 0 if current_month_revenue == 0 else 100
    
    # Get last 6 months for trend
    six_months_ago = now - timedelta(days=180)
    monthly_trend = {}
    
    for i in range(6):
        month_date = now - timedelta(days=30 * i)
        month_key = month_date.strftime('%Y-%m')
        month_orders = Order.query.filter(
            Order.date >= datetime(month_date.year, month_date.month, 1),
            Order.date < datetime(month_date.year, month_date.month, 1) + timedelta(days=32),
            Order.status != 'Cancelled'
        ).all()
        
        monthly_revenue = sum(
            item.quantity * item.unit_price_sold
            for order in month_orders
            for item in order.items
        )
        monthly_trend[month_key] = monthly_revenue
    
    # Sort by month
    sorted_trend = sorted(monthly_trend.items(), reverse=True)
    
    return jsonify({
        'current_month': current_month,
        'current_month_revenue': current_month_revenue,
        'last_month': last_month,
        'last_month_revenue': last_month_revenue,
        'growth_percentage': growth_percentage,
        'trend_labels': [month[0] for month in sorted_trend],
        'trend_revenues': [monthly_trend[month[0]] for month in sorted_trend]
    })


@main.route('/api/chart/product-profit-margin')
def api_chart_product_profit_margin():
    """API endpoint para gráfico de margen de ganancia por producto"""
    now = datetime.utcnow()
    twelve_months_ago = now - timedelta(days=365)
    
    # Query all order items in the last 12 months
    order_items = OrderItem.query.join(Order).filter(
        Order.date >= twelve_months_ago,
        Order.status != 'Cancelled'
    ).all()
    
    # Aggregate by product
    product_data = {}
    for item in order_items:
        if not item.product:
            continue
        product_id = item.product.id
        product_name = item.product.name
        
        if product_id not in product_data:
            product_data[product_id] = {
                'name': product_name,
                'revenue': 0,
                'cost': 0,
                'quantity': 0
            }
        
        product_data[product_id]['revenue'] += item.quantity * item.unit_price_sold
        product_data[product_id]['cost'] += item.quantity * item.unit_production_cost_snapshot
        product_data[product_id]['quantity'] += item.quantity
    
    # Calculate profit margins
    product_margins = []
    for product_id, data in product_data.items():
        if data['revenue'] > 0:
            profit = data['revenue'] - data['cost']
            margin_percentage = (profit / data['revenue']) * 100
            product_margins.append({
                'name': data['name'],
                'revenue': data['revenue'],
                'cost': data['cost'],
                'profit': profit,
                'margin_percentage': margin_percentage,
                'quantity': data['quantity']
            })
    
    # Sort by profit and take top 10
    sorted_products = sorted(product_margins, key=lambda x: x['profit'], reverse=True)[:10]
    
    return jsonify({
        'labels': [p['name'] for p in sorted_products],
        'profits': [p['profit'] for p in sorted_products],
        'margins': [p['margin_percentage'] for p in sorted_products],
        'revenues': [p['revenue'] for p in sorted_products]
    })


# ==================== SALES & ORDERS ====================

@main.route('/sales')
@login_required
def sales():
    """Vista de ventas con historial"""
    orders = Order.query.order_by(Order.date.desc()).all()
    customers = Customer.query.all()
    products = Product.query.all()
    config = GlobalConfig.get_singleton()
    
    return render_template('sales.html', 
                          orders=orders, 
                          customers=customers, 
                          products=products,
                          config=config)


@main.route('/api/sales/create', methods=['POST'])
def api_sales_create():
    """Crear una nueva orden de venta"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('items') or len(data['items']) == 0:
            return jsonify({'error': 'No items in order'}), 400
        
        customer_id = data.get('customer_id')
        customer = Customer.query.get(customer_id) if customer_id else None
        
        # Create or update customer if needed
        if not customer and data.get('customer_name'):
            customer = Customer(
                full_name=data['customer_name'],
                channel=data.get('channel', 'Local'),
                phone=data.get('customer_phone'),
                email=data.get('customer_email')
            )
            db.session.add(customer)
            db.session.flush()
        
        # Create order
        order = Order(
            customer_id=customer.id if customer else None,
            date=datetime.utcnow(),
            status='Pending',
            payment_method=data.get('payment_method', 'Efectivo'),
            platform_fee_percentage=data.get('platform_fee_percentage', 0.0)
        )
        
        config = GlobalConfig.get_singleton()
        total_billed = 0.0
        
        # Process items
        for item_data in data['items']:
            product_id = item_data.get('product_id')
            quantity = item_data.get('quantity', 1)
            unit_price = item_data.get('unit_price')
            
            product = Product.query.get_or_404(product_id)
            
            # Check stock for all materials
            if product.materials:
                # Multi-material support
                for pm in product.materials:
                    required_weight = pm.weight_grams * quantity
                    if pm.material and pm.material.current_weight < required_weight:
                        return jsonify({'error': f'Insufficient stock for {pm.material.brand} {pm.material.color} in product {product.name}'}), 400
            else:
                # Legacy single material
                required_weight = product.slicer_weight * quantity
                if product.default_material and product.default_material.current_weight < required_weight:
                    return jsonify({'error': f'Insufficient stock for {product.name}'}), 400
            
            # Calculate cost snapshot
            costs = product.calculate_production_cost(config)
            unit_cost = costs['total']
            
            # Create order item
            order_item = OrderItem(
                product_id=product_id,
                quantity=quantity,
                unit_production_cost_snapshot=unit_cost,
                unit_price_sold=unit_price
            )
            order.items.append(order_item)
            
            # Deduct stock immediately - multi-material support
            if product.materials:
                for pm in product.materials:
                    required_weight = pm.weight_grams * quantity
                    if pm.material:
                        old_weight = pm.material.current_weight
                        pm.material.current_weight -= required_weight
                        print(f"DEBUG: Stock deduction - Material: {pm.material.brand} {pm.material.color}, Old: {old_weight}g, Deducted: {required_weight}g, New: {pm.material.current_weight}g")
            else:
                # Legacy single material
                required_weight = product.slicer_weight * quantity
                if product.default_material:
                    old_weight = product.default_material.current_weight
                    product.default_material.current_weight -= required_weight
                    print(f"DEBUG: Stock deduction - Material: {product.default_material.brand} {product.default_material.color}, Old: {old_weight}g, Deducted: {required_weight}g, New: {product.default_material.current_weight}g")
            
            # Update printer hours
            if product.default_printer:
                product.default_printer.accumulated_hours += product.print_time_hours * quantity
            
            total_billed += unit_price * quantity
        
        order.total_amount_billed = total_billed
        order.status = 'In Production'  # Auto-transition to production
        
        db.session.add(order)
        db.session.commit()
        
        print(f"DEBUG: Order created - ID: {order.id}, Status: {order.status}")
        
        return jsonify({
            'success': True,
            'order_id': order.id,
            'total_billed': order.total_amount_billed,
            'profit': order.net_profit
        }), 201
    
    except Exception as e:
        db.session.rollback()
        print(f"ERROR: Failed to create order - {str(e)}")
        return jsonify({'error': str(e)}), 500


@main.route('/api/sales/list')
def api_sales_list():
    """Listar órdenes de venta con filtros"""
    status = request.args.get('status')
    channel = request.args.get('channel')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = Order.query
    
    if status:
        query = query.filter_by(status=status)
    if channel:
        query = query.join(Customer).filter(Customer.channel == channel)
    if date_from:
        query = query.filter(Order.date >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Order.date <= datetime.fromisoformat(date_to))
    
    orders = query.order_by(Order.date.desc()).all()
    
    return jsonify([{
        'id': o.id,
        'customer': o.customer.full_name if o.customer else 'Counter Sale',
        'date': o.date.isoformat(),
        'status': o.status,
        'amount_billed': o.total_amount_billed,
        'production_cost': o.total_production_cost,
        'profit': o.net_profit,
        'items_count': len(o.items)
    } for o in orders])


@main.route('/api/sales/<int:order_id>/update-status', methods=['POST'])
def api_sales_update_status(order_id):
    """Actualizar estado de una orden"""
    order = Order.query.get_or_404(order_id)
    new_status = request.json.get('status')
    
    if new_status not in ['Pending', 'In Production', 'Ready', 'Delivered', 'Cancelled']:
        return jsonify({'error': 'Invalid status'}), 400
    
    order.status = new_status
    db.session.commit()
    
    return jsonify({'success': True, 'status': order.status})


# ==================== PRODUCTS & INVENTORY ====================

@main.route('/inventory')
@login_required
def inventory():
    """Vista de inventario"""
    products = Product.query.all()
    materials = Material.query.all()
    config = GlobalConfig.get_singleton()
    
    return render_template('inventory.html', 
                          products=products, 
                          materials=materials,
                          config=config)


@main.route('/api/products')
def api_products():
    """Lista de productos con costos"""
    products = Product.query.all()
    config = GlobalConfig.get_singleton()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'category': p.category,
        'description': p.description,
        'retail_price': p.retail_price,
        'slicer_weight': p.slicer_weight,
        'material_cost': p.material_cost,
        'print_time': p.print_time_hours,
        'power_consumption': p.power_consumption,
        'postproc_time': p.post_process_hours,
        'printer_id': p.default_printer_id,
        'additional_costs': p.additional_costs,
        'production_cost': p.calculate_production_cost(config)['total'],
        'suggested_price': p.suggested_price,
        'image_url': p.image_url,
        'images': [img.image_url for img in p.images] if hasattr(p, 'images') else [],
        'enable_quantity_discounts': p.enable_quantity_discounts,
        'visible': p.visible,
        'quantity_discounts_json': p.quantity_discounts_json
    } for p in products])


@main.route('/api/products/<int:product_id>')
def api_product_detail(product_id):
    """Detalle completo de un producto"""
    product = Product.query.get_or_404(product_id)
    config = GlobalConfig.get_singleton()
    costs = product.calculate_production_cost(config)
    
    return jsonify({
        'id': product.id,
        'name': product.name,
        'slicer_weight': product.slicer_weight,
        'print_time': product.print_time_hours,
        'postproc_time': product.post_process_hours,
        'material': product.default_material.color if product.default_material else None,
        'printer': product.default_printer.name if product.default_printer else None,
        'costs': costs,
        'suggested_price': product.suggested_price,
        'additional_costs': product.additional_costs
    })


@main.route('/api/products/create', methods=['POST'])
def api_products_create():
    """Crear nuevo producto"""
    try:
        data = request.get_json()
        
        product = Product(
            name=data['name'],
            category=data.get('category', 'General'),
            description=data.get('description'),
            retail_price=data.get('retail_price', 0),
            slicer_weight=data.get('slicer_weight', 0),
            material_cost=data.get('material_cost', 0),
            print_time_hours=data.get('print_time_hours', 0),
            power_consumption=data.get('power_consumption', 0),
            post_process_hours=data.get('post_process_hours', 0),
            default_material_id=data.get('material_id'),
            default_printer_id=data.get('printer_id'),
            additional_costs=data.get('additional_costs', 0),
            image_url=data.get('image_url'),
            enable_quantity_discounts=data.get('enable_quantity_discounts', True),
            visible=data.get('visible', True),
            quantity_discounts_json=data.get('quantity_discounts_json')
        )
        
        db.session.add(product)
        db.session.flush()  # Flush to get product ID
        
        # Handle multiple materials if provided
        materials_data = data.get('materials', [])
        if materials_data:
            total_weight = 0
            for mat_data in materials_data:
                pm = ProductMaterial(
                    product_id=product.id,
                    material_id=mat_data['material_id'],
                    weight_grams=mat_data['weight_grams']
                )
                db.session.add(pm)
                total_weight += mat_data['weight_grams']
            
            # Update slicer_weight with total from materials
            product.slicer_weight = total_weight
        
        # Handle multiple images if provided
        images_data = data.get('images', [])
        if images_data:
            for i, img_url in enumerate(images_data):
                pi = ProductImage(
                    product_id=product.id,
                    image_url=img_url,
                    sort_order=i
                )
                db.session.add(pi)
            
            # Set legacy image_url to first image for backward compatibility
            product.image_url = images_data[0]
        
        db.session.commit()
        
        return jsonify({'success': True, 'product_id': product.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/products/<int:product_id>', methods=['PUT'])
@login_required
def api_products_update(product_id):
    """Actualizar producto existente"""
    try:
        product = Product.query.get_or_404(product_id)
        data = request.get_json()
        
        product.name = data.get('name', product.name)
        product.category = data.get('category', product.category)
        product.description = data.get('description', product.description)
        product.retail_price = data.get('retail_price', product.retail_price)
        product.slicer_weight = data.get('slicer_weight', product.slicer_weight)
        product.material_cost = data.get('material_cost', product.material_cost)
        product.print_time_hours = data.get('print_time_hours', product.print_time_hours)
        product.power_consumption = data.get('power_consumption', product.power_consumption)
        product.post_process_hours = data.get('post_process_hours', product.post_process_hours)
        product.default_material_id = data.get('material_id', product.default_material_id)
        product.default_printer_id = data.get('printer_id', product.default_printer_id)
        product.additional_costs = data.get('additional_costs', product.additional_costs)
        product.image_url = data.get('image_url', product.image_url)
        product.enable_quantity_discounts = data.get('enable_quantity_discounts', product.enable_quantity_discounts)
        product.visible = data.get('visible', product.visible)
        product.quantity_discounts_json = data.get('quantity_discounts_json')
        
        # Handle multiple materials
        materials_data = data.get('materials', [])
        if materials_data:
            # Delete existing materials
            ProductMaterial.query.filter_by(product_id=product.id).delete()
            
            total_weight = 0
            for mat_data in materials_data:
                pm = ProductMaterial(
                    product_id=product.id,
                    material_id=mat_data['material_id'],
                    weight_grams=mat_data['weight_grams']
                )
                db.session.add(pm)
                total_weight += mat_data['weight_grams']
            
            product.slicer_weight = total_weight
        
        # Handle multiple images
        images_data = data.get('images', [])
        if images_data:
            # Delete existing images
            ProductImage.query.filter_by(product_id=product.id).delete()
            
            for i, img_url in enumerate(images_data):
                pi = ProductImage(
                    product_id=product.id,
                    image_url=img_url,
                    sort_order=i
                )
                db.session.add(pi)
            
            product.image_url = images_data[0]
        
        db.session.commit()
        
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/products/<int:product_id>', methods=['DELETE'])
@login_required
def api_products_delete(product_id):
    """Eliminar producto"""
    try:
        product = Product.query.get_or_404(product_id)
        db.session.delete(product)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/materials')
def api_materials():
    """Lista de materiales en stock"""
    materials = Material.query.all()
    
    return jsonify([{
        'id': m.id,
        'brand': m.brand,
        'type': m.type,
        'color': m.color,
        'total_weight': m.total_weight,
        'current_weight': m.current_weight,
        'remaining_percent': m.remaining_percent,
        'cost_per_gram': m.cost_per_gram,
        'status': m.stock_status,
        'purchase_cost': m.purchase_cost
    } for m in materials])


@main.route('/api/materials/create', methods=['POST'])
def api_materials_create():
    """Crear nuevo material"""
    try:
        data = request.get_json()
        
        material = Material(
            brand=data['brand'],
            type=data['type'],
            color=data['color'],
            total_weight=data.get('total_weight', 1000),
            current_weight=data.get('current_weight', 1000),
            purchase_cost=data.get('purchase_cost', 0),
            supplier_id=data.get('supplier_id')
        )
        
        db.session.add(material)
        db.session.commit()
        
        return jsonify({'success': True, 'material_id': material.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/materials/<int:material_id>')
def api_material_detail(material_id):
    """Detalle de un material"""
    material = Material.query.get_or_404(material_id)
    
    return jsonify({
        'id': material.id,
        'brand': material.brand,
        'type': material.type,
        'color': material.color,
        'total_weight': material.total_weight,
        'current_weight': material.current_weight,
        'remaining_percent': material.remaining_percent,
        'cost_per_gram': material.cost_per_gram,
        'status': material.stock_status,
        'purchase_cost': material.purchase_cost,
        'supplier_id': material.supplier_id
    })


@main.route('/api/materials/<int:material_id>', methods=['PUT'])
@login_required
def api_materials_update(material_id):
    """Actualizar material existente"""
    try:
        material = Material.query.get_or_404(material_id)
        data = request.get_json()
        
        material.brand = data.get('brand', material.brand)
        material.type = data.get('type', material.type)
        material.color = data.get('color', material.color)
        material.total_weight = data.get('total_weight', material.total_weight)
        material.current_weight = data.get('current_weight', material.current_weight)
        material.purchase_cost = data.get('purchase_cost', material.purchase_cost)
        material.supplier_id = data.get('supplier_id', material.supplier_id)
        
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/materials/<int:material_id>', methods=['DELETE'])
@login_required
def api_materials_delete(material_id):
    """Eliminar material"""
    try:
        material = Material.query.get_or_404(material_id)
        
        # Check if material is used in any product
        product_materials = ProductMaterial.query.filter_by(material_id=material_id).all()
        if product_materials:
            return jsonify({'error': 'No se puede eliminar el material porque está siendo usado en productos'}), 400
        
        db.session.delete(material)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ==================== WASTE TRACKING ====================

@main.route('/api/waste/log', methods=['POST'])
def api_waste_log():
    """Registrar desperdicio"""
    try:
        data = request.get_json()
        
        material = Material.query.get_or_404(data['material_id'])
        waste_grams = data.get('weight_wasted', 0)
        
        # Deduct from stock
        material.current_weight = max(0, material.current_weight - waste_grams)
        
        # Log the waste
        waste_log = WasteLog(
            material_id=data['material_id'],
            weight_wasted=waste_grams,
            reason=data.get('reason', 'Unspecified failure')
        )
        
        db.session.add(waste_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'cost_impact': waste_log.cost_impact,
            'remaining_weight': material.current_weight
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ==================== USER MANAGEMENT ====================

@main.route('/users')
@login_required
def user_management():
    """Página de gestión de usuarios"""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('user_management.html', users=users)


@main.route('/api/users')
@login_required
def api_users_list():
    """Listar usuarios"""
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'role': u.role,
        'is_first_login': u.is_first_login,
        'created_at': u.created_at.isoformat()
    } for u in users])


@main.route('/api/users/<int:user_id>')
@login_required
def api_user_get(user_id):
    """Obtener usuario por ID"""
    user = User.query.get_or_404(user_id)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'role': user.role,
        'is_first_login': user.is_first_login,
        'created_at': user.created_at.isoformat()
    })


@main.route('/api/users/create', methods=['POST'])
@login_required
def api_user_create():
    """Crear nuevo usuario"""
    try:
        data = request.get_json()
        
        if not data.get('username') or not data.get('password'):
            return jsonify({'error': 'Usuario y contraseña son requeridos'}), 400
        
        # Verificar si el usuario ya existe
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'El usuario ya existe'}), 400
        
        user = User(
            username=data['username'],
            role=data.get('role', 'vendedor')
        )
        user.set_password(data['password'])
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'success': True, 'user_id': user.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
def api_user_update(user_id):
    """Actualizar usuario"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        
        if data.get('username'):
            # Verificar si el nuevo username ya existe
            existing = User.query.filter_by(username=data['username']).first()
            if existing and existing.id != user_id:
                return jsonify({'error': 'El usuario ya existe'}), 400
            user.username = data['username']
        
        if data.get('role'):
            user.role = data['role']
        
        if data.get('password'):
            user.set_password(data['password'])
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
def api_user_delete(user_id):
    """Eliminar usuario"""
    try:
        user = User.query.get_or_404(user_id)
        
        # No permitir eliminar al usuario admin actual
        if user.username == 'admin':
            return jsonify({'error': 'No se puede eliminar el usuario admin'}), 400
        
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ==================== CUSTOMER ORDERS ====================

@main.route('/customer-orders')
@login_required
def customer_orders():
    """Página de gestión de órdenes de clientes"""
    orders = CustomerOrder.query.order_by(CustomerOrder.created_at.desc()).all()
    return render_template('customer_orders.html', orders=orders)


@main.route('/api/customer-orders/<int:order_id>/confirm', methods=['POST'])
@login_required
def api_customer_order_confirm(order_id):
    """Confirmar orden de cliente y convertirla en venta"""
    try:
        customer_order = CustomerOrder.query.get_or_404(order_id)
        if customer_order.status != 'Pendiente':
            return jsonify({'error': 'Solo se pueden confirmar órdenes pendientes'}), 400
        
        # Crear o actualizar cliente
        customer = Customer.query.filter_by(phone=customer_order.customer_phone).first()
        if not customer:
            customer = Customer(
                full_name=customer_order.customer_name,
                channel='Web',
                phone=customer_order.customer_phone,
                email=customer_order.customer_email
            )
            db.session.add(customer)
            db.session.flush()
        
        # Crear orden de venta
        order = Order(
            customer_id=customer.id,
            date=datetime.utcnow(),
            status='In Production',
            payment_method='Efectivo',
            platform_fee_percentage=0.0
        )
        
        config = GlobalConfig.get_singleton()
        total_billed = 0.0
        
        # Procesar items de la orden de cliente
        for item in customer_order.items:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 1)
            unit_price = item.get('unit_price')
            
            product = Product.query.get_or_404(product_id)
            
            # Verificar stock para todos los materiales
            if product.materials:
                for pm in product.materials:
                    required_weight = pm.weight_grams * quantity
                    if pm.material and pm.material.current_weight < required_weight:
                        return jsonify({'error': f'Stock insuficiente para {pm.material.brand} {pm.material.color} en producto {product.name}'}), 400
            else:
                required_weight = product.slicer_weight * quantity
                if product.default_material and product.default_material.current_weight < required_weight:
                    return jsonify({'error': f'Stock insuficiente para {product.name}'}), 400
            
            # Calcular costo snapshot
            costs = product.calculate_production_cost(config)
            unit_cost = costs['total']
            
            # Crear item de orden
            order_item = OrderItem(
                product_id=product_id,
                quantity=quantity,
                unit_production_cost_snapshot=unit_cost,
                unit_price_sold=unit_price
            )
            order.items.append(order_item)
            
            # Deduct stock - soporte multi-material
            if product.materials:
                for pm in product.materials:
                    required_weight = pm.weight_grams * quantity
                    if pm.material:
                        old_weight = pm.material.current_weight
                        pm.material.current_weight -= required_weight
            else:
                required_weight = product.slicer_weight * quantity
                if product.default_material:
                    old_weight = product.default_material.current_weight
                    product.default_material.current_weight -= required_weight
            
            # Actualizar horas de impresora
            if product.default_printer:
                product.default_printer.accumulated_hours += product.print_time_hours * quantity
            
            total_billed += unit_price * quantity
        
        order.total_amount_billed = total_billed
        
        # Actualizar estado de la orden de cliente
        customer_order.status = 'Confirmada'
        
        db.session.add(order)
        db.session.commit()
        
        return jsonify({'success': True, 'order_id': order.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/customer-orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def api_customer_order_cancel(order_id):
    """Cancelar orden de cliente"""
    try:
        order = CustomerOrder.query.get_or_404(order_id)
        if order.status != 'Pendiente':
            return jsonify({'error': 'Solo se pueden cancelar órdenes pendientes'}), 400
        
        order.status = 'Cancelada'
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/customer-orders/<int:order_id>', methods=['DELETE'])
@login_required
def api_customer_order_delete(order_id):
    """Eliminar orden de cliente"""
    try:
        order = CustomerOrder.query.get_or_404(order_id)
        db.session.delete(order)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ==================== EXPENSES / GASTOS ====================

@main.route('/expenses')
@login_required
def expenses():
    """Página de gestión de gastos"""
    expenses = Expense.query.order_by(Expense.date.desc()).all()
    materials = Material.query.all()
    return render_template('expenses.html', expenses=expenses, materials=materials)


@main.route('/api/expenses')
def api_expenses_list():
    """Listar gastos con filtros"""
    category = request.args.get('category')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = Expense.query
    
    if category:
        query = query.filter(Expense.category == category)
    if date_from:
        query = query.filter(Expense.date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Expense.date <= datetime.strptime(date_to, '%Y-%m-%d'))
    
    expenses = query.order_by(Expense.date.desc()).all()
    
    return jsonify([{
        'id': e.id,
        'date': e.date.strftime('%Y-%m-%d %H:%M'),
        'category': e.category,
        'description': e.description,
        'amount': e.amount,
        'supplier': e.supplier.name if e.supplier else None,
        'material': f"{e.material.brand} {e.material.color}" if e.material else None,
        'receipt_url': e.receipt_url,
        'notes': e.notes
    } for e in expenses])


@main.route('/api/expenses/create', methods=['POST'])
def api_expenses_create():
    """Crear nuevo gasto"""
    try:
        data = request.get_json()
        
        expense = Expense(
            date=datetime.strptime(data['date'], '%Y-%m-%d') if data.get('date') else datetime.utcnow(),
            category=data['category'],
            description=data['description'],
            amount=data['amount'],
            supplier_id=data.get('supplier_id'),
            material_id=data.get('material_id'),
            receipt_url=data.get('receipt_url'),
            notes=data.get('notes')
        )
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify({'success': True, 'expense_id': expense.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
def api_expenses_delete(expense_id):
    """Eliminar un gasto"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        db.session.delete(expense)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ==================== CATALOG EXPORT ====================

@main.route('/catalogo/export')
def catalog_export():
    """Exportar catálogo estático como HTML"""
    products = Product.query.all()
    config = GlobalConfig.get_singleton()
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Catálogo de Productos - Taller 3D</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ padding: 20px; background-color: #f8f9fa; }}
        .product-card {{ 
            background: white; 
            border-radius: 10px; 
            padding: 20px; 
            margin-bottom: 20px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
            transition: transform 0.2s;
        }}
        .product-card:hover {{ transform: translateY(-5px); }}
        .product-image {{ 
            width: 100%; 
            height: 200px; 
            object-fit: cover; 
            border-radius: 8px; 
            margin-bottom: 15px;
            background-color: #e9ecef;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #6c757d;
            overflow: hidden;
        }}
        .product-image img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            max-width: 100%;
            max-height: 200px;
        }}
        .price {{ 
            font-size: 1.5em; 
            font-weight: bold; 
            color: #28a745; 
        }}
        .header {{ 
            text-align: center; 
            margin-bottom: 40px; 
            padding: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 15px;
        }}
        .info-badge {{
            display: inline-block;
            padding: 5px 10px;
            background-color: #e9ecef;
            border-radius: 20px;
            margin: 5px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎨 Catálogo de Productos 3D</h1>
            <p>Impresiones de alta calidad a medida</p>
            <small>Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}</small>
        </div>
        
        <div class="row">
"""
    
    for product in products:
        costs = product.calculate_production_cost(config)
        image_html = f'<img src="{product.image_url}" alt="{product.name}">' if product.image_url else '<span>Sin imagen</span>'
        description_html = f'<p class="text-muted small">{product.description}</p>' if product.description else ''
        
        # Calcular precios mayoristas
        price_5 = product.get_wholesale_price(5)
        price_10 = product.get_wholesale_price(10)
        price_25 = product.get_wholesale_price(25)
        
        html += f"""
            <div class="col-md-4 col-sm-6">
                <div class="product-card">
                    <div class="product-image">
                        {image_html}
                    </div>
                    <h4>{product.name}</h4>
                    {description_html}
                    <p class="price">${product.retail_price if product.retail_price > 0 else product.suggested_price:.2f} <small class="text-muted">(1 unidad)</small></p>
                    <div class="mt-3">
                        <span class="info-badge">⚖️ {product.slicer_weight}g</span>
                        <span class="info-badge">⏱️ {product.print_time_hours:.1f}h</span>
                        <span class="info-badge">🔧 {product.default_material.color if product.default_material else 'N/A'}</span>
                    </div>
                    <div class="mt-3">
                        <p class="small mb-1"><strong>Precios por cantidad:</strong></p>
                        <div class="small">
                            <span class="badge bg-secondary">+5: ${price_5:.2f}</span>
                            <span class="badge bg-secondary">+10: ${price_10:.2f}</span>
                            <span class="badge bg-secondary">+25: ${price_25:.2f}</span>
                        </div>
                    </div>
                    <p class="text-muted mt-2 small">
                        Costo de producción: ${costs['total']:.2f}
                    </p>
                </div>
            </div>
"""
    
    html += """
        </div>
        
        <footer class="text-center mt-5 mb-3 text-muted">
            <p>Taller de Impresión 3D - Contáctenos para pedidos personalizados</p>
        </footer>
    </div>
</body>
</html>
"""
    
    response = Response(html, mimetype='text/html')
    response.headers['Content-Disposition'] = 'attachment; filename=catalogo_productos.html'
    return response


# ==================== CONFIGURATION ====================

@main.route('/config')
@login_required
def config_page():
    """Página de configuración"""
    config = GlobalConfig.get_singleton()
    suppliers = Supplier.query.all()
    printers = Printer.query.all()
    maintenance_logs = MaintenanceLog.query.order_by(MaintenanceLog.date.desc()).limit(20).all()
    materials = Material.query.all()
    
    return render_template('config.html', 
                          config=config,
                          suppliers=suppliers,
                          printers=printers,
                          maintenance_logs=maintenance_logs,
                          materials=materials)


@main.route('/api/config/update', methods=['POST'])
def api_config_update():
    """Actualizar configuración global"""
    try:
        config = GlobalConfig.get_singleton()
        data = request.get_json()
        
        if 'kwh_cost' in data:
            config.kwh_cost = data['kwh_cost']
        if 'labor_hour_cost' in data:
            config.labor_hour_cost = data['labor_hour_cost']
        if 'base_profit_margin' in data:
            config.base_profit_margin = data['base_profit_margin']
        if 'fail_margin_multiplier' in data:
            config.fail_margin_multiplier = data['fail_margin_multiplier']
        if 'wholesale_discounts_json' in data:
            config.wholesale_discounts_json = data['wholesale_discounts_json']
        if 'payment_methods_json' in data:
            config.payment_methods_json = data['payment_methods_json']
        if 'company_name' in data:
            config.company_name = data['company_name']
        if 'company_logo_url' in data:
            config.company_logo_url = data['company_logo_url']
        if 'instagram_url' in data:
            config.instagram_url = data['instagram_url']
        if 'whatsapp_url' in data:
            config.whatsapp_url = data['whatsapp_url']
        
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/printers')
def api_printers():
    """Lista de impresoras"""
    printers = Printer.query.all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'power_consumption': p.power_consumption,
        'purchase_price': p.purchase_price,
        'estimated_lifespan': p.estimated_lifespan,
        'accumulated_hours': p.accumulated_hours,
        'status': p.status,
        'depreciation_per_hour': p.depreciation_per_hour,
        'needs_maintenance': p.needs_maintenance
    } for p in printers])


@main.route('/api/categories', methods=['GET', 'POST'])
def api_categories():
    """Lista o crea categorías"""
    if request.method == 'GET':
        categories = Category.query.all()
        return jsonify([{
            'id': c.id,
            'name': c.name,
            'description': c.description
        } for c in categories])
    elif request.method == 'POST':
        try:
            data = request.get_json()
            category = Category(
                name=data['name'],
                description=data.get('description', '')
            )
            db.session.add(category)
            db.session.commit()
            return jsonify({'success': True, 'id': category.id})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400


@main.route('/api/categories/<int:category_id>', methods=['PUT', 'DELETE'])
def api_category_detail(category_id):
    """Actualiza o elimina una categoría"""
    category = Category.query.get_or_404(category_id)
    
    if request.method == 'PUT':
        try:
            data = request.get_json()
            category.name = data.get('name', category.name)
            category.description = data.get('description', category.description)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400
    elif request.method == 'DELETE':
        try:
            db.session.delete(category)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400


@main.route('/api/printers/create', methods=['POST'])
def api_printers_create():
    """Crear nueva impresora"""
    try:
        data = request.get_json()
        
        printer = Printer(
            name=data['name'],
            power_consumption=data.get('power_consumption', 180),
            purchase_price=data.get('purchase_price', 0),
            estimated_lifespan=data.get('estimated_lifespan', 5000),
            status=data.get('status', 'Active')
        )
        
        db.session.add(printer)
        db.session.commit()
        
        return jsonify({'success': True, 'printer_id': printer.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/maintenance/log', methods=['POST'])
def api_maintenance_log():
    """Registrar mantenimiento"""
    try:
        data = request.get_json()
        
        printer = Printer.query.get_or_404(data['printer_id'])
        
        maintenance = MaintenanceLog(
            printer_id=data['printer_id'],
            description=data.get('description', ''),
            cost=data.get('cost', 0)
        )
        
        printer.last_maintenance = datetime.utcnow()
        
        db.session.add(maintenance)
        db.session.commit()
        
        return jsonify({'success': True}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ==================== PUBLIC CATALOG ====================

def cleanup_expired_orders():
    """Eliminar órdenes de clientes expiradas automáticamente"""
    expired_orders = CustomerOrder.query.filter(
        CustomerOrder.status == 'Pendiente',
        CustomerOrder.expires_at < datetime.utcnow()
    ).all()
    
    for order in expired_orders:
        db.session.delete(order)
    
    if expired_orders:
        db.session.commit()
        print(f"DEBUG: Deleted {len(expired_orders)} expired customer orders")
    
    return len(expired_orders)


@main.route('/catalogo')
def public_catalog():
    """Catálogo público para clientes"""
    products = Product.query.filter_by(visible=True).all()
    config = GlobalConfig.get_singleton()
    
    return render_template('public_catalog.html', products=products, config=config)


@main.route('/api/customer-orders/create', methods=['POST'])
def api_customer_orders_create():
    """Crear orden de cliente desde el catálogo público"""
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        if not data.get('customer_name') or not data.get('customer_phone'):
            return jsonify({'error': 'Nombre y teléfono son requeridos'}), 400
        
        if not data.get('items') or len(data['items']) == 0:
            return jsonify({'error': 'La orden debe tener al menos un item'}), 400
        
        # Calcular fecha de expiración (48 horas)
        expires_at = datetime.utcnow() + timedelta(hours=48)
        
        # Crear orden de cliente
        customer_order = CustomerOrder(
            customer_name=data['customer_name'],
            customer_phone=data['customer_phone'],
            customer_email=data.get('customer_email'),
            status='Pendiente',
            expires_at=expires_at,
            items_json=json.dumps(data['items']),
            total_amount=data.get('total_amount', 0)
        )
        
        db.session.add(customer_order)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'order_id': customer_order.id,
            'expires_at': expires_at.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@main.route('/api/customer-orders')
@login_required
def api_customer_orders_list():
    """Listar órdenes de clientes"""
    orders = CustomerOrder.query.order_by(CustomerOrder.created_at.desc()).all()
    return jsonify([{
        'id': o.id,
        'customer_name': o.customer_name,
        'customer_phone': o.customer_phone,
        'customer_email': o.customer_email,
        'status': o.status,
        'created_at': o.created_at.isoformat(),
        'expires_at': o.expires_at.isoformat() if o.expires_at else None,
        'is_expired': o.is_expired,
        'items': o.items,
        'total_amount': o.total_amount
    } for o in orders])


# ==================== LOGIN / AUTHENTICATION ====================

@main.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"DEBUG: Login attempt - Username: {username}")
        
        user = User.query.filter_by(username=username).first()
        
        print(f"DEBUG: User found: {user is not None}")
        if user:
            print(f"DEBUG: User username: {user.username}")
            print(f"DEBUG: Password hash exists: {user.password_hash is not None}")
        
        if user and user.check_password(password):
            print(f"DEBUG: Password check successful")
            login_user(user)
            return redirect(url_for('main.dashboard'))
        else:
            print(f"DEBUG: Password check failed or user not found")
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')


@main.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    return redirect(url_for('main.login'))


@main.route('/setup', methods=['GET', 'POST'])
def setup():
    """Crear usuario admin inicial automáticamente"""
    try:
        user_count = User.query.count()
        print(f"DEBUG: Setup route - User count: {user_count}")
        
        if user_count > 0:
            print(f"DEBUG: Setup route - Users already exist, redirecting to login")
            return redirect(url_for('main.login'))
        
        # Crear usuario admin automáticamente
        print(f"DEBUG: Setup route - Creating admin user")
        user = User(username='admin', role='admin', is_first_login=True)
        user.set_password('1234')
        db.session.add(user)
        db.session.commit()
        
        print(f"DEBUG: Setup route - Admin user created successfully")
        flash('Usuario admin creado automáticamente. Usuario: admin, Contraseña: 1234', 'success')
        return redirect(url_for('main.login'))
    except Exception as e:
        print(f"DEBUG: Setup route - Error: {e}")
        db.session.rollback()
        flash(f'Error al crear usuario admin: {e}', 'error')
        return redirect(url_for('main.login'))


# ==================== REPORTS ====================

@main.route('/reports')
@login_required
def reports():
    """Página de reportes"""
    return render_template('reports.html')


@main.route('/api/reports')
@login_required
def api_reports():
    """API para obtener datos de reportes"""
    report_type = request.args.get('type', 'daily')
    period_offset = int(request.args.get('offset', 0))
    specific_date = request.args.get('date')
    
    now = datetime.utcnow()
    if specific_date:
        now = datetime.strptime(specific_date, '%Y-%m-%d')
    
    # Calculate date range based on report type and offset
    if report_type == 'daily':
        start_date = now - timedelta(days=period_offset)
        end_date = start_date + timedelta(days=1)
    elif report_type == 'weekly':
        start_date = now - timedelta(weeks=period_offset)
        start_date = start_date - timedelta(days=start_date.weekday())  # Start of week (Monday)
        end_date = start_date + timedelta(weeks=1)
    else:  # monthly
        start_date = now - timedelta(days=period_offset * 30)
        start_date = datetime(start_date.year, start_date.month, 1)
        if start_date.month == 12:
            end_date = datetime(start_date.year + 1, 1, 1)
        else:
            end_date = datetime(start_date.year, start_date.month + 1, 1)
    
    # Query orders in the date range
    orders = Order.query.filter(
        Order.date >= start_date,
        Order.date < end_date,
        Order.status != 'Cancelled'
    ).all()
    
    # Calculate totals
    total_revenue = sum(o.total_amount_billed or 0 for o in orders)
    total_orders = len(orders)
    total_products = sum(len(o.items) for o in orders)
    total_profit = sum(
        sum((item.unit_price_sold - item.unit_production_cost_snapshot) * item.quantity for item in o.items)
        for o in orders
    )
    
    # Revenue by day
    revenue_by_day = {}
    for order in orders:
        day_key = order.date.strftime('%Y-%m-%d')
        revenue_by_day[day_key] = revenue_by_day.get(day_key, 0) + (order.total_amount_billed or 0)
    
    # Top products
    product_counts = {}
    for order in orders:
        for item in order.items:
            product_name = item.product.name if item.product else 'Unknown'
            product_counts[product_name] = product_counts.get(product_name, 0) + item.quantity
    
    top_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Prepare orders data for table
    orders_data = []
    for order in orders:
        products_list = ', '.join([item.product.name if item.product else 'Unknown' for item in order.items])
        quantity = sum(item.quantity for item in order.items)
        orders_data.append({
            'date': order.date.isoformat(),
            'customer_name': order.customer.full_name if order.customer else '-',
            'products': products_list,
            'quantity': quantity,
            'total': order.total_amount_billed or 0,
            'status': order.status
        })
    
    return jsonify({
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'total_products': total_products,
        'total_profit': total_profit,
        'revenue_by_day': {
            'labels': sorted(revenue_by_day.keys()),
            'data': [revenue_by_day[k] for k in sorted(revenue_by_day.keys())]
        },
        'top_products': {
            'labels': [p[0] for p in top_products],
            'data': [p[1] for p in top_products]
        },
        'orders': orders_data
    })