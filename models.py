from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from enum import Enum as PyEnum

db = SQLAlchemy()


class Supplier(db.Model):
    """Proveedores de materia prima (filamentos, resinas, etc.)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    contact = db.Column(db.String(200))
    phone = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    materials = db.relationship('Material', backref='supplier', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Supplier {self.name}>'


class Material(db.Model):
    """Filamentos, resinas y otros materiales para impresión"""
    __tablename__ = 'material'
    
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # PLA, ABS, PETG, TPU, etc.
    color = db.Column(db.String(50), nullable=False)
    total_weight = db.Column(db.Float, default=1000.0, nullable=False)  # gramos
    current_weight = db.Column(db.Float, default=1000.0, nullable=False)  # gramos remanentes
    purchase_cost = db.Column(db.Float, default=0.0, nullable=False)  # $ pagados por el rollo
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=True)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    products = db.relationship('Product', backref='default_material', foreign_keys='Product.default_material_id')

    @property
    def cost_per_gram(self):
        """Costo unitario calculado dinámicamente"""
        try:
            return self.purchase_cost / self.total_weight if self.total_weight > 0 else 0.0
        except:
            return 0.0

    @property
    def remaining_percent(self):
        """Porcentaje del material remanente"""
        if self.total_weight:
            return max(0.0, min(100.0, (self.current_weight / self.total_weight) * 100.0))
        return 0.0

    @property
    def stock_status(self):
        """Estado visual del stock: 'critical', 'low', 'normal'"""
        pct = self.remaining_percent
        if pct < 15:
            return 'critical'
        elif pct < 50:
            return 'low'
        return 'normal'

    def __repr__(self):
        return f'<Material {self.brand} {self.type} {self.color}>'


class Printer(db.Model):
    """Máquinas impresoras (Bambu Lab, Ender3, etc.)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    power_consumption = db.Column(db.Float, default=180.0, nullable=False)  # Watts
    purchase_price = db.Column(db.Float, default=0.0, nullable=False)  # Costo de adquisición
    estimated_lifespan = db.Column(db.Float, default=5000.0, nullable=False)  # Horas útiles
    accumulated_hours = db.Column(db.Float, default=0.0)  # Horas acumuladas de uso
    status = db.Column(db.String(50), default='Active')  # Active, Maintenance, Inactive
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_maintenance = db.Column(db.DateTime, nullable=True)
    
    products = db.relationship('Product', backref='default_printer', foreign_keys='Product.default_printer_id')
    maintenance_logs = db.relationship('MaintenanceLog', backref='printer', cascade='all, delete-orphan')

    @property
    def depreciation_per_hour(self):
        """Costo de depreciación por hora de uso"""
        try:
            return self.purchase_price / self.estimated_lifespan if self.estimated_lifespan > 0 else 0.0
        except:
            return 0.0

    @property
    def hours_since_maintenance(self):
        """Horas desde el último mantenimiento"""
        if self.last_maintenance:
            return self.accumulated_hours - (self.last_maintenance - self.purchase_date).total_seconds() / 3600
        return self.accumulated_hours

    @property
    def needs_maintenance(self):
        """¿Requiere mantenimiento? (umbral: 500+ horas desde último service)"""
        hours = self.hours_since_maintenance
        return hours >= 500 if hours is not None else False

    def __repr__(self):
        return f'<Printer {self.name}>'


class MaintenanceLog(db.Model):
    """Historial de mantenimiento de máquinas"""
    id = db.Column(db.Integer, primary_key=True)
    printer_id = db.Column(db.Integer, db.ForeignKey('printer.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=False)
    cost = db.Column(db.Float, default=0.0)  # Costo del mantenimiento
    
    def __repr__(self):
        return f'<MaintenanceLog Printer {self.printer_id} on {self.date}>'


class Product(db.Model):
    """Catálogo de diseños / productos finales a imprimir"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    slicer_weight = db.Column(db.Float, default=0.0, nullable=False)  # Gramos según laminador
    print_time_hours = db.Column(db.Float, default=0.0, nullable=False)  # Formato decimal
    post_process_hours = db.Column(db.Float, default=0.0, nullable=False)  # Horas de trabajo manual
    default_material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=True)
    default_printer_id = db.Column(db.Integer, db.ForeignKey('printer.id'), nullable=True)
    additional_costs = db.Column(db.Float, default=0.0)  # Tornillos, imanes, packaging, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def calculate_production_cost(self, config=None):
        """
        Calcula el costo total de producción para UNA unidad del producto.
        Fórmula: material + electricity + depreciation + labor + additional
        """
        if config is None:
            config = GlobalConfig.get_singleton()
        
        filament = self.default_material
        printer = self.default_printer
        
        # Costo de filamento
        material_cost = (self.slicer_weight or 0.0) * (filament.cost_per_gram if filament else 0.0)
        
        # Costo de electricidad: (Watts / 1000) * Horas * $/kWh
        electricity_cost = ((printer.power_consumption if printer else 0.0) / 1000.0) * \
                          (self.print_time_hours or 0.0) * \
                          (config.kwh_cost if config else 0.1)
        
        # Costo de depreciación de máquina
        depreciation_cost = (self.print_time_hours or 0.0) * \
                           (printer.depreciation_per_hour if printer else 0.0)
        
        # Costo de mano de obra
        labor_cost = (self.post_process_hours or 0.0) * (config.labor_hour_cost if config else 10.0)
        
        total = material_cost + electricity_cost + depreciation_cost + labor_cost + (self.additional_costs or 0.0)
        
        return {
            'material': round(material_cost, 4),
            'electricity': round(electricity_cost, 4),
            'depreciation': round(depreciation_cost, 4),
            'labor': round(labor_cost, 4),
            'additional': round(self.additional_costs or 0.0, 4),
            'total': round(total, 4)
        }

    @property
    def suggested_price(self):
        """Precio de venta sugerido = costo * (1 + margen%)"""
        config = GlobalConfig.get_singleton()
        costs = self.calculate_production_cost(config)
        base_cost = costs['total']
        margin_factor = 1.0 + ((config.base_profit_margin or 150.0) / 100.0)
        return round(base_cost * margin_factor, 2)

    def __repr__(self):
        return f'<Product {self.name}>'


class Customer(db.Model):
    """Clientes que realizan compras"""
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    channel = db.Column(db.String(50))  # Instagram, WhatsApp, Local, Web, etc.
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    orders = db.relationship('Order', backref='customer', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Customer {self.full_name}>'


class Order(db.Model):
    """Órdenes de venta (encabezado)"""
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Pending')  # Pending, In Production, Ready, Delivered, Cancelled
    payment_method = db.Column(db.String(50))  # Efectivo, Transferencia, Mercado Pago, etc.
    platform_fee_percentage = db.Column(db.Float, default=0.0)  # Comisión por canal
    total_amount_billed = db.Column(db.Float, default=0.0)  # Precio final real vendido
    
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')

    @property
    def total_production_cost(self):
        """Costo total de producción para todos los items"""
        config = GlobalConfig.get_singleton()
        total = 0.0
        for item in self.items:
            if item.product:
                costs = item.product.calculate_production_cost(config)
                total += costs['total'] * (item.quantity or 1)
        return round(total, 2)

    @property
    def platform_fee_amount(self):
        """Monto de comisión por canal de venta"""
        return round((self.total_amount_billed or 0.0) * (self.platform_fee_percentage or 0.0) / 100.0, 2)

    @property
    def gross_profit(self):
        """Ganancia bruta = ingresos - costos de producción"""
        return round((self.total_amount_billed or 0.0) - self.total_production_cost, 2)

    @property
    def net_profit(self):
        """Ganancia neta = ganancia bruta - comisión por plataforma"""
        return round(self.gross_profit - self.platform_fee_amount, 2)

    def __repr__(self):
        return f'<Order {self.id} - {self.status}>'


class OrderItem(db.Model):
    """Detalle de items dentro de una orden"""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_production_cost_snapshot = db.Column(db.Float, default=0.0)  # Costo al momento de venta
    unit_price_sold = db.Column(db.Float, default=0.0)  # Precio unitario cobrado
    
    product = db.relationship('Product')

    @property
    def total_cost(self):
        """Costo total para este item (cantidad * costo unitario)"""
        return round((self.unit_production_cost_snapshot or 0.0) * (self.quantity or 1), 2)

    @property
    def total_revenue(self):
        """Ingresos totales para este item (cantidad * precio vendido)"""
        return round((self.unit_price_sold or 0.0) * (self.quantity or 1), 2)

    @property
    def item_profit(self):
        """Ganancia en este item"""
        return round(self.total_revenue - self.total_cost, 2)

    def __repr__(self):
        return f'<OrderItem Order {self.order_id} - Product {self.product_id}>'


class WasteLog(db.Model):
    """Control de fallas, desperdicio y material perdido"""
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    weight_wasted = db.Column(db.Float, default=0.0, nullable=False)  # Gramos perdidos
    reason = db.Column(db.String(200), nullable=False)  # Falta de adherencia, corte de luz, etc.
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    material = db.relationship('Material')

    @property
    def cost_impact(self):
        """Impacto financiero de este desperdicio"""
        if self.material:
            return round(self.weight_wasted * self.material.cost_per_gram, 4)
        return 0.0

    def __repr__(self):
        return f'<WasteLog {self.weight_wasted}g on {self.date}>'


class GlobalConfig(db.Model):
    """Configuración global del sistema"""
    __tablename__ = 'global_config'
    
    id = db.Column(db.Integer, primary_key=True)
    kwh_cost = db.Column(db.Float, default=0.12)  # $ por kWh
    labor_hour_cost = db.Column(db.Float, default=15.0)  # $ por hora de trabajo
    base_profit_margin = db.Column(db.Float, default=150.0)  # Porcentaje de ganancia base
    fail_margin_multiplier = db.Column(db.Float, default=1.05)  # Factor de recargo por riesgo
    
    @classmethod
    def get_singleton(cls):
        """Obtiene o crea la configuración única del sistema"""
        cfg = cls.query.first()
        if not cfg:
            cfg = cls()
            db.session.add(cfg)
            db.session.commit()
        return cfg

    def __repr__(self):
        return '<GlobalConfig>'
