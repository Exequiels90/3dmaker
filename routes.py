from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from models import (db, Product, Material, Printer, GlobalConfig, Order, OrderItem, 
                    Customer, WasteLog, MaintenanceLog, Supplier)
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import json

main = Blueprint('main', __name__)


# ==================== DASHBOARD & ANALYTICS ====================

@main.route('/')
def index():
    return redirect(url_for('main.dashboard'))


@main.route('/dashboard')
def dashboard():
    """Dashboard principal con KPIs"""
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
    
    # KPI 2: Net profit (revenue - production costs - platform fees)
    monthly_costs = sum(o.total_production_cost for o in month_orders)
    monthly_fees = sum(o.platform_fee_amount for o in month_orders)
    monthly_profit = monthly_revenue - monthly_costs - monthly_fees
    
    # KPI 3: Total kg of filament in stock
    total_filament_kg = sum(m.current_weight for m in Material.query.all()) / 1000.0
    
    # KPI 4: Active alerts (low stock + maintenance needed)
    # remaining_percent and needs_maintenance are Python @property, not DB columns,
    # so filtering must happen in Python after fetching all records.
    low_stock_materials = sum(1 for m in Material.query.all() if m.remaining_percent < 15)
    printers_needing_maintenance = sum(1 for p in Printer.query.all() if p.needs_maintenance)
    total_alerts = low_stock_materials + printers_needing_maintenance
    
    context = {
        'monthly_revenue': round(monthly_revenue, 2),
        'orders_count': orders_count,
        'monthly_profit': round(monthly_profit, 2),
        'total_filament_kg': round(total_filament_kg, 2),
        'total_alerts': total_alerts,
        'low_stock_count': low_stock_materials,
        'maintenance_count': printers_needing_maintenance,
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


# ==================== SALES & ORDERS ====================

@main.route('/sales')
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
            
            # Check stock
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
            
            # Deduct stock immediately
            if product.default_material:
                product.default_material.current_weight -= required_weight
            
            # Update printer hours
            if product.default_printer:
                product.default_printer.accumulated_hours += product.print_time_hours * quantity
            
            total_billed += unit_price * quantity
        
        order.total_amount_billed = total_billed
        order.status = 'In Production'  # Auto-transition to production
        
        db.session.add(order)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'order_id': order.id,
            'total_billed': order.total_amount_billed,
            'profit': order.net_profit
        }), 201
    
    except Exception as e:
        db.session.rollback()
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
        'slicer_weight': p.slicer_weight,
        'print_time': p.print_time_hours,
        'postproc_time': p.post_process_hours,
        'production_cost': p.calculate_production_cost(config)['total'],
        'suggested_price': p.suggested_price
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
            slicer_weight=data.get('slicer_weight', 0),
            print_time_hours=data.get('print_time_hours', 0),
            post_process_hours=data.get('post_process_hours', 0),
            default_material_id=data.get('material_id'),
            default_printer_id=data.get('printer_id'),
            additional_costs=data.get('additional_costs', 0)
        )
        
        db.session.add(product)
        db.session.commit()
        
        return jsonify({'success': True, 'product_id': product.id}), 201
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


# ==================== CONFIGURATION ====================

@main.route('/config')
def config_page():
    """Página de configuración"""
    config = GlobalConfig.get_singleton()
    suppliers = Supplier.query.all()
    printers = Printer.query.all()
    maintenance_logs = MaintenanceLog.query.order_by(MaintenanceLog.date.desc()).limit(20).all()
    
    return render_template('config.html', 
                          config=config,
                          suppliers=suppliers,
                          printers=printers,
                          maintenance_logs=maintenance_logs)


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