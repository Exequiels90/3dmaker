from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
from enum import Enum as PyEnum
import bcrypt
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Usuario del sistema para login"""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='vendedor', nullable=False)  # admin, vendedor
    is_first_login = db.Column(db.Boolean, default=False, nullable=False)  # Para usuario admin inicial
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Cifrar contraseña usando bcrypt"""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def check_password(self, password):
        """Verificar contraseña usando bcrypt"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def __repr__(self):
        return f'<User {self.username}>'


class Category(db.Model):
    """Categoría de productos"""
    __tablename__ = 'category'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Category {self.name}>'


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


class ProductMaterial(db.Model):
    """Tabla de asociación para productos multi-material"""
    __tablename__ = 'product_material'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    weight_grams = db.Column(db.Float, default=0.0, nullable=False)  # Gramos de este material para el producto
    
    material = db.relationship('Material')
    
    def __repr__(self):
        return f'<ProductMaterial Product {self.product_id} - Material {self.material_id}>'


class ProductImage(db.Model):
    """Imágenes de productos (soporta múltiples imágenes por producto)"""
    __tablename__ = 'product_image'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)  # Orden de visualización
    
    product = db.relationship('Product', backref=db.backref('images', lazy=True, cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<ProductImage {self.product_id} - {self.image_url}>'


class Product(db.Model):
    """Catálogo de diseños / productos finales a imprimir"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)  # Descripción para el catálogo
    category = db.Column(db.String(100), nullable=True, default='General')  # Categoría del producto
    slicer_weight = db.Column(db.Float, default=0.0, nullable=False)  # Gramos según laminador (legacy, se calcula desde ProductMaterial)
    material_cost = db.Column(db.Float, default=0.0)  # Costo directo del laminado ($)
    print_time_hours = db.Column(db.Float, default=0.0, nullable=False)  # Formato decimal
    post_process_hours = db.Column(db.Float, default=0.0, nullable=False)  # Horas de trabajo manual
    default_material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=True)  # Legacy para compatibilidad
    default_printer_id = db.Column(db.Integer, db.ForeignKey('printer.id'), nullable=True)
    power_consumption = db.Column(db.Float, default=0.0)  # Consumo de energía en Watts (si no usa el de la impresora)
    additional_costs = db.Column(db.Float, default=0.0)  # Tornillos, imanes, packaging, etc.
    image_url = db.Column(db.String(500), nullable=True)  # URL de imagen del producto
    retail_price = db.Column(db.Float, default=0.0)  # Precio minorista (precio base)
    enable_quantity_discounts = db.Column(db.Boolean, default=True)  # Habilitar descuentos por cantidad
    quantity_discounts_json = db.Column(db.Text, nullable=True)  # Descuentos por cantidad personalizados (JSON)
    visible = db.Column(db.Boolean, default=True)  # Visible en el catálogo público
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    materials = db.relationship('ProductMaterial', backref='product', cascade='all, delete-orphan')

    def calculate_production_cost(self, config=None):
        """
        Calcula el costo total de producción para UNA unidad del producto.
        Fórmula: material + electricity + depreciation + labor + additional
        """
        if config is None:
            config = GlobalConfig.get_singleton()
        
        printer = self.default_printer
        
        # Costo de filamento - usar costo directo si está definido, si no usar materiales legacy
        if self.material_cost and self.material_cost > 0:
            material_cost = self.material_cost
        elif self.materials:
            material_cost = sum(pm.weight_grams * (pm.material.cost_per_gram if pm.material else 0.0) for pm in self.materials)
        else:
            # Fallback a legacy default_material
            filament = self.default_material
            material_cost = (self.slicer_weight or 0.0) * (filament.cost_per_gram if filament else 0.0)
        
        # Costo de electricidad: (Watts / 1000) * Horas * $/kWh
        # Usar power_consumption del producto si está definido, si no usar el de la impresora
        power_watts = self.power_consumption if self.power_consumption and self.power_consumption > 0 else (printer.power_consumption if printer else 0.0)
        electricity_cost = (power_watts / 1000.0) * \
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
    def total_weight(self):
        """Peso total del producto sumando todos los materiales"""
        if self.materials:
            return sum(pm.weight_grams for pm in self.materials)
        return self.slicer_weight or 0.0

    @property
    def suggested_price(self):
        """Precio de venta sugerido = costo * (1 + margen%)"""
        config = GlobalConfig.get_singleton()
        costs = self.calculate_production_cost(config)
        base_cost = costs['total']
        margin_factor = 1.0 + ((config.base_profit_margin or 150.0) / 100.0)
        return round(base_cost * margin_factor, 2)
    
    def get_wholesale_price(self, quantity):
        """Calcular precio mayorista según cantidad"""
        # Si tiene precio minorista definido, usarlo como base
        base_price = self.retail_price if self.retail_price > 0 else self.suggested_price
        
        config = GlobalConfig.get_singleton()
        discount = 0.0
        
        # Si el producto tiene descuentos personalizados, usarlos
        if self.quantity_discounts_json:
            try:
                product_discounts = json.loads(self.quantity_discounts_json)
                for rule in sorted(product_discounts, key=lambda x: x.get('threshold', 0), reverse=True):
                    if quantity >= rule.get('threshold', 0) and rule.get('enabled', True):
                        discount = rule.get('discount', 0)
                        break
            except:
                pass
        
        # Si no tiene descuentos personalizados o no se encontró ninguno, usar los globales
        if discount == 0.0 and config.wholesale_discounts_json:
            try:
                global_discounts = json.loads(config.wholesale_discounts_json)
                for rule in sorted(global_discounts, key=lambda x: x.get('threshold', 0), reverse=True):
                    if quantity >= rule.get('threshold', 0) and rule.get('enabled', True):
                        discount = rule.get('discount', 0)
                        break
            except:
                pass
        
        return round(base_price * (1 - discount / 100.0), 2)

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
    wholesale_discounts_json = db.Column(db.Text, default='[{"threshold": 5, "discount": 10, "enabled": true}, {"threshold": 10, "discount": 15, "enabled": true}, {"threshold": 25, "discount": 20, "enabled": true}]')  # Descuentos por cantidad (JSON)
    payment_methods_json = db.Column(db.Text, default='["Efectivo", "Mercado Pago", "Transferencia"]')  # Métodos de pago (JSON)
    company_name = db.Column(db.String(100), default='3D System')  # Nombre de la empresa
    company_logo_url = db.Column(db.String(500), nullable=True)  # URL del logo de la empresa
    instagram_url = db.Column(db.String(500), nullable=True)  # URL de Instagram
    
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


class Expense(db.Model):
    """Egresos / Gastos del sistema"""
    __tablename__ = 'expense'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # Filamento, Accesorio, Packaging, etc.
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, default=0.0, nullable=False)  # Monto total del gasto ($)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=True)
    receipt_url = db.Column(db.String(500), nullable=True)  # URL de foto del ticket/factura
    notes = db.Column(db.Text, nullable=True)
    
    supplier = db.relationship('Supplier')
    material = db.relationship('Material')
    
    def __repr__(self):
        return f'<Expense {self.category} - ${self.amount}>'


class CustomerOrder(db.Model):
    """Órdenes de clientes desde el catálogo web público"""
    __tablename__ = 'customer_order'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(200), nullable=False)
    customer_phone = db.Column(db.String(50), nullable=False)
    customer_email = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(50), default='Pendiente', nullable=False)  # Pendiente, Confirmada, Cancelada
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)  # Fecha de expiración (48hs)
    
    # Items de la orden (JSON con productos, cantidades y precios)
    items_json = db.Column(db.Text, nullable=False)
    total_amount = db.Column(db.Float, default=0.0, nullable=False)
    
    @property
    def items(self):
        """Parsear items JSON"""
        import json
        return json.loads(self.items_json) if self.items_json else []
    
    @property
    def is_expired(self):
        """Verificar si la orden expiró"""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        return False
    
    def __repr__(self):
        return f'<CustomerOrder {self.id} - {self.customer_name} - {self.status}>'
