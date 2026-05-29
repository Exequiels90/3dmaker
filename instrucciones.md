# PROMPT DE INGENIERÍA DE SOFTWARE: SISTEMA WEB INTEGRAL DE COSTOS, STOCK, VENTAS Y MANTENIMIENTO 3D

## 1. CONTEXTO, FILOSOFÍA Y OBJETIVO DEL SISTEMA
Necesito desarrollar una aplicación web de nivel profesional para la gestión total de un taller de impresión 3D (producción y comercialización). El sistema debe erradicar por completo las estimaciones "a ojo" y automatizar el cálculo del costo real por gramo, consumo eléctrico preciso, amortización de hardware, tiempos de mano de obra y el impacto financiero del descarte (impresiones fallidas).

### Stack Tecnológico Requerido:
- **Backend:** Flask (Python 3.10+) utilizando una estructura limpia y modular (Blueprints / Application Factory).
- **Base de Datos:** SQLite para la etapa de desarrollo (mapeada rigurosamente con Flask-SQLAlchemy).
- **Frontend:** Plantilla AdminLTE v3 integrada mediante Jinja2, basada en Bootstrap 4/5, FontAwesome, DataTables para grillas avanzadas y Chart.js para analítica visual.

---

## 2. ARQUITECTURA DE DATOS REQUERIDA (MODELOS RELACIONALES)
Genera los modelos de SQLAlchemy con restricciones de clave foránea (`ForeignKey`), cascadas de eliminación correctas y propiedades calculadas (`@property`) en el backend.

### A. Módulo de Proveedores y Materia Prima (Stock)
*   **Tabla `Supplier` (Proveedores):**
    *   `id` (Integer, PK)
    *   `name` (String, Not Null) - ej. "Filamentos Región"
    *   `contact_phone` / `email` (String)
*   **Tabla `Material` (Filamentos / Resinas):**
    *   `id` (Integer, PK)
    *   `brand` (String, Not Null) - ej. "GST", "Grilon3", "Hellbot"
    *   `type` (String, Not Null) - ej. "PLA", "ABS", "PETG", "TPU"
    *   `color` (String, Not Null)
    *   `total_weight` (Float) - Peso inicial del rollo en gramos (ej. 1000.0)
    *   `current_weight` (Float) - Peso neto remanente en gramos.
    *   `purchase_cost` (Float) - Precio pagado por el rollo ($).
    *   `supplier_id` (Integer, FK -> `Supplier`)
    *   **Propiedad Calculada:** `cost_per_gram` -> (`purchase_cost` / `total_weight`).

### B. Módulo de Infraestructura y Producción
*   **Tabla `Printer` (Máquinas):**
    *   `id` (Integer, PK)
    *   `name` (String, Not Null) - ej. "Bambu Lab A1 Combo", "Ender 3 S1"
    *   `power_consumption` (Integer) - Consumo promedio real en Watts (ej. 180W).
    *   `purchase_price` (Float) - Costo de adquisición de la máquina ($).
    *   `estimated_lifespan` (Integer) - Horas útiles estimadas antes de recambio mayor (ej. 5000).
    *   `accumulated_hours` (Float) - Horas totales de uso registradas por el sistema.
    *   `status` (Enum: 'Active', 'Maintenance', 'Inactive')
    *   **Propiedad Calculada:** `depreciation_per_hour` -> (`purchase_price` / `estimated_lifespan`).
*   **Tabla `MaintenanceLog` (Historial de Service):**
    *   `id` (Integer, PK)
    *   `printer_id` (Integer, FK -> `Printer`)
    *   `date` (DateTime)
    *   `description` (Text) - ej. "Cambio de nozzle de acero endurecido, tensión de correas".
    *   `cost` (Float) - Costo del repuesto/mantenimiento (debe sumarse a los costos fijos globales).

### C. Módulo de Catálogo y Costeo Prerregistrado
*   **Tabla `Product` (Diseños / Productos Finales):**
    *   `id` (Integer, PK)
    *   `name` (String, Not Null) - ej. "Chopp Boca Juniors", "Mate Térmico"
    *   `slicer_weight` (Float) - Gramos requeridos según el laminador (incluyendo soportes/balsa).
    *   `print_time_hours` (Float) - Tiempo estimado de impresión en formato decimal (ej. 2.5 horas).
    *   `post_process_hours` (Float) - Tiempo de trabajo manual requerido (remoción de soportes, lijado, pintura, armado).
    *   `default_material_id` (Integer, FK -> `Material`)
    *   `default_printer_id` (Integer, FK -> `Printer`)
    *   `additional_costs` (Float) - Costo de insumos no impresos (tornillos, imanes, packaging, cajas, bolsas).
    *   **Fórmulas Críticas de Costeo (Calculadas dinámicamente en el backend):**
        *   `material_cost` = `slicer_weight` * `Material.cost_per_gram`
        *   `electricity_cost` = (`Printer.power_consumption` / 1000) * `print_time_hours` * `GlobalConfig.kwh_cost`
        *   `depreciation_cost` = `print_time_hours` * `Printer.depreciation_per_hour`
        *   `labor_cost` = `post_process_hours` * `GlobalConfig.labor_hour_cost`
        *   `total_production_cost` = `material_cost` + `electricity_cost` + `depreciation_cost` + `labor_cost` + `additional_costs`
        *   `suggested_price_base` = `total_production_cost` * (1 + `GlobalConfig.base_profit_margin` / 100)

### D. Módulo de Ventas, Clientes y Descarte (¡Esencial!)
*   **Tabla `Customer` (Clientes):**
    *   `id` (Integer, PK)
    *   `full_name` (String, Not Null)
    *   `channel` (String) - Vía de contacto (ej. "Instagram", "WhatsApp", "Local").
*   **Tabla `Order` (Historial de Ventas Ejecutadas):**
    *   `id` (Integer, PK)
    *   `customer_id` (Integer, FK -> `Customer`, Nullable=True)
    *   `date` (DateTime, Default=Now)
    *   `status` (Enum: 'Pending', 'In Production', 'Ready', 'Delivered', 'Cancelled')
    *   `payment_method` (String) - ej. "Efectivo", "Transferencia", "Mercado Pago"
    *   `platform_fee_percentage` (Float) - Comisión del canal de venta usado para esa transacción.
    *   `total_amount_billed` (Float) - El precio final real al que se vendió la orden.
*   **Tabla `OrderItem` (Detalle de la Orden):**
    *   `id` (Integer, PK)
    *   `order_id` (Integer, FK -> `Order`)
    *   `product_id` (Integer, FK -> `Product`)
    *   `quantity` (Integer)
    *   `unit_production_cost_snapshot` (Float) - Copia congelada del costo de producción al momento de la venta (para auditoría histórica).
    *   `unit_price_sold` (Float) - Precio unitario real cobrado.
*   **Tabla `WasteLog` (Control de Fallas / Desperdicio):**
    *   `id` (Integer, PK)
    *   `material_id` (Integer, FK -> `Material`)
    *   `weight_wasted` (Float) - Gramos perdidos (ej. spaghetti, pieza despegada).
    *   `reason` (String) - Motivo (ej. "Falta de adherencia", "Corte de luz", "Nudo en rollo").
    *   `date` (DateTime)

### E. Configuración del Sistema
*   **Tabla `GlobalConfig`:**
    *   `id` (Integer, PK)
    *   `kwh_cost` (Float) - Precio de la energía eléctrica.
    *   `labor_hour_cost` (Float) - Cuánto vale tu hora de trabajo técnico/manual.
    *   `base_profit_margin` (Float) - Porcentaje de ganancia base (ej. 150%).
    *   `fail_margin_multiplier` (Float) - Factor de recargo por riesgo de falla estándar (ej. 1.05 para añadir un 5% al costo base).

---

## 3. LÓGICA DE NEGOCIO Y DISPARADORES (TRIGGERS / BACKEND FLASK)
El backend debe implementar estrictamente las siguientes reglas operativas:

1.  **Validación Pre-Producción / Pre-Venta:** Antes de cambiar una orden a estado `'In Production'` o guardar una venta directa, el sistema debe verificar si hay suficiente `current_weight` en el `Material` asignado. Si falta stock, debe lanzar un mensaje flash (`flash('Stock insuficiente de filamento X', 'danger')`) y bloquear la acción.
2.  **Descuento Automático de Stock:** Al procesar y confirmar la producción de un `OrderItem`, el sistema debe restar automáticamente:
    `Material.current_weight = Material.current_weight - (Product.slicer_weight * Quantity)`.
3.  **Impacto del Descarte (Waste):** Cuando se registra una falla en `WasteLog`, los gramos se restan inmediatamente del stock del material, y su costo equivalente (`weight_wasted * cost_per_gram`) se marca como pérdida neta en los balances financieros.
4.  **Actualización de Horas de Máquina:** Al finalizar una orden, el tiempo acumulado (`Product.print_time_hours * Quantity`) debe sumarse a `Printer.accumulated_hours`. Si supera un umbral de 500 horas desde el último service, se debe disparar una notificación visual en el Dashboard.

---

## 4. DISEÑO DE INTERFAZ Y UX (ADMINLTE INTERACTIVE)
El frontend debe usar layouts heredados con Jinja2. Quiero pantallas sumamente visuales que utilicen los componentes nativos de AdminLTE.

### Vista 1: Dashboard Analítico e Indicadores Clave (KPIs)
- **Bloques de Información Rápida (Small Boxes con Iconos):**
  - **Caja 1 (Verde):** Facturación total del mes en curso ($) + Contador de Órdenes.
  - **Caja 2 (Azul):** Ganancia Neta Real acumulada del mes (Ingresos - Costos de Producción - Comisiones - Pérdidas por Fallas).
  - **Caja 3 (Amarilla):** Kilogramos totales de filamento en stock actual (Suma de todos los `current_weight` / 1000).
  - **Caja 4 (Roja):** Alertas activas (Rollos por acabarse < 15% o impresoras que requieren mantenimiento técnico).
- **Sección Gráfica Interactiva (Chart.js):**
  - **Gráfico A (Barras Dobles):** "Ingresos vs Costos Totales" agrupados por mes, mostrando visualmente el punto de equilibrio.
  - **Gráfico B (Dona / Pie):** "Distribución del Costo de un Producto". Un dropdown dinámico permite elegir un producto del catálogo y el gráfico se actualiza por AJAX mostrando el % exacto que se lleva el filamento, la luz, la mano de obra, la amortización y los extras.
  - **Gráfico C (Línea de Tendencia):** Tasa de descarte/fallas mensual en gramos de filamento perdidos.

### Vista 2: Panel de Ventas y Facturación Realizada
- **Filtros Avanzados:** Por rango de fechas, canal de venta (Instagram, Web) y estado de la orden utilizando DataTables.
- **Formulario de Nueva Venta Avanzado:**
  - Selección de cliente (o creación rápida "Cliente Mostrador").
  - Selector dinámico de productos mediante filas clonables con Javascript.
  - Al seleccionar un producto, mostrar en tiempo real al costado el "Precio de Venta Sugerido", permitiendo al usuario modificar el "Precio Final Cobrado" en caso de aplicar un descuento o recargo manual.
  - Campo de selección para "Canal de Venta" para calcular comisiones financieras en el acto.

### Vista 3: Catálogo Dinámico de Costos de Productos
- Una grilla con DataTables donde se listen los diseños impresos. 
- Cada fila debe exhibir el costo de producción crudo y el precio sugerido de venta.
- Un botón **"Ver Desglose"** debe desplegar un modal estilizado de AdminLTE que contenga una tabla limpia:
  | Componente de Costo | Valor Calculado ($) | Porcentaje del Total |
  | :--- | :--- | :--- |
  | Filamento Usado | $XX.XX | XX% |
  | Energía Eléctrica | $XX.XX | XX% |
  | Desgaste de Impresora | $XX.XX | XX% |
  | Tiempo de Mano de Obra | $XX.XX | XX% |
  | Componentes Adicionales | $XX.XX | XX% |

### Vista 4: Inventario de Filamentos con Barra de Progreso
- Listado de rollos. El stock remanente se debe representar de forma sumamente visual mediante una **Progress Bar de Bootstrap** que cambie de color según el estado:
  - Verde si el rollo tiene > 50% de material.
  - Amarillo si está entre el 15% y el 50%.
  - Rojo parpadeante si está por debajo del 15%.

---

## 5. ENTREGABLES TÉCNICOS SOLICITADOS
Para construir el sistema de forma inmediata, proporcióname:
1. La **estructura de directorios y archivos** recomendada siguiendo el patrón Application Factory de Flask.
2. El archivo de modelos (`models.py`) completo utilizando SQLAlchemy con todas las tablas descritas, relaciones bien mapeadas y los métodos decorados con `@property` que ejecuten los cálculos exactos de costos.
3. El archivo de rutas de la API (`api_routes.py`) que devuelva las estructuras JSON formateadas requeridas por Chart.js para renderizar los gráficos del dashboard sin retrasos.
4. La plantilla HTML base del Dashboard (`dashboard.html`) estructurada bajo las clases CSS de AdminLTE v3, configurando el contenedor de los gráficos y la inicialización de Chart.js con llamadas `fetch()`.
---

## 6. MEJORAS PENDIENTES Y BACKLOG (Sesión 2026-05-29)

### 🐛 BUGS CONOCIDOS A CORREGIR

#### Bug 1: Descuento de stock no funciona al crear producto/orden
- Al registrar una orden con un producto de 100g, el `current_weight` del material NO se deduce.
- **Causa probable:** La lógica de descuento en `routes.py` (endpoint `api_sales_create`) posiblemente solo descuenta cuando la orden cambia a estado `'Delivered'` o `'In Production'`, pero no en la creación directa, o bien la condición de estado nunca se cumple.
- **Fix requerido:** Revisar el endpoint `POST /api/sales/create` y `POST /api/sales/<id>/update-status`. El descuento debe ejecutarse al confirmar/crear la orden, iterando `order.items` y restando `product.slicer_weight * item.quantity` del `material.current_weight` correspondiente. Agregar logs de debug para verificar.

#### Bug 2: Producto mono-material (limitación de diseño)
- El modelo `Product` solo acepta `default_material_id` (un único material).
- Las impresoras multicolor (ej. Bambu Lab A1 Combo con AMS) requieren múltiples filamentos por producto.
- **Ejemplo real:** Un producto puede usar 10g blanco BambuLab + 40g negro Grilon3 + 50g azul GST Black Edition.

---

### ✨ NUEVAS FUNCIONALIDADES A IMPLEMENTAR

#### Feature 1: Soporte Multi-Material por Producto (PRIORIDAD ALTA)

**Cambio en modelos (`models.py`):**
- Crear nueva tabla `ProductMaterial` (tabla de asociación):
  - `id` (Integer, PK)
  - `product_id` (Integer, FK -> `Product`)
  - `material_id` (Integer, FK -> `Material`)
  - `weight_grams` (Float) — gramos de ese filamento para este producto
- `Product` mantiene `default_material_id` como opcional/legacy pero se agrega relación:
  - `materials = db.relationship('ProductMaterial', backref='product', cascade='all, delete-orphan')`
- Recalcular `material_cost` en `calculate_production_cost()` sumando todos los `ProductMaterial`:
  ```python
  material_cost = sum(pm.weight_grams * pm.material.cost_per_gram for pm in self.materials)
  ```
- El descuento de stock al vender debe iterar TODOS los `ProductMaterial` del producto.

**Cambio en frontend (`inventory.html`):**
- En el formulario "Add/Edit Product", reemplazar el selector único de material por una sección dinámica con filas clonables (similar al formulario de nueva venta):
  - Cada fila: `[Material dropdown] [Gramos] [Eliminar fila]`
  - Botón "+ Agregar material"
  - Total de gramos calculado en tiempo real

**Cambio en rutas (`routes.py`):**
- `api_products_create` y eventual `api_products_update` deben aceptar `materials: [{material_id, weight_grams}, ...]` en el JSON.

---

#### Feature 2: Campo URL de Imagen por Producto (PRIORIDAD MEDIA)

**Objetivo:** No almacenar imágenes en SQLite. El usuario sube fotos a OneDrive/Google Drive/Imgur u otra nube gratuita, copia la URL pública y la pega en el sistema.

**Cambio en modelos (`models.py`):**
```python
# En clase Product, agregar columna:
image_url = db.Column(db.String(500), nullable=True)
```

**Cambio en frontend:**
- En el formulario de producto: campo de texto `image_url` con placeholder `https://...`
- En la grilla de productos: mostrar thumbnail pequeño `<img src="{{ product.image_url }}" style="height:40px">` si tiene URL, o ícono placeholder si no.
- En el modal de desglose de costos: mostrar imagen en tamaño mayor.

**Servicios de imagen gratuitos recomendados para documentar al usuario:**
- OneDrive: compartir archivo → "Cualquiera con el enlace" → copiar enlace directo
- Google Drive: compartir → enlace público → convertir a `https://drive.google.com/uc?id=FILE_ID`
- Imgur: subida directa, URL pública inmediata
- Cloudinary: plan gratuito 25GB

---

#### Feature 3: Catálogo Estático Exportable (PRIORIDAD BAJA — Fase Futura)

**Objetivo:** Generar un sitio web estático (HTML/CSS/JS sin backend) que funcione como catálogo de productos para clientes, usando los datos del sistema + las URLs de imágenes.

**Opciones de implementación a evaluar:**
1. **Ruta Flask `/catalogo/export`** que genere un `.zip` con `index.html` estático + assets usando Jinja2 para renderizar los productos con sus imágenes, precios sugeridos y descripción.
2. **Script standalone `export_catalog.py`** que conecta a la BD SQLite y genera los archivos estáticos.

**Datos a incluir en el catálogo:**
- Nombre del producto
- Imagen (desde `image_url`)
- Precio de venta sugerido (sin mostrar costos internos)
- Materiales disponibles / colores
- (Opcional) Formulario de contacto que apunte a WhatsApp/Instagram

**Stack sugerido para el catálogo estático:**
- HTML + TailwindCSS CDN (sin dependencias locales)
- Grid de tarjetas responsive
- Filtro por tipo de producto con JavaScript vanilla
- Deployable en GitHub Pages, Netlify Free, o simplemente enviable como ZIP al cliente

---

### 📋 RESUMEN DE ARCHIVOS A MODIFICAR POR FEATURE

| Feature | Archivos a modificar |
|---|---|
| Bug fix stock descuento | `routes.py` (endpoint create/update-status) |
| Multi-material | `models.py` (nueva tabla), `routes.py` (crear/editar producto), `inventory.html` (formulario) |
| URL de imagen | `models.py` (+1 columna), `routes.py` (serialización), `inventory.html` (form + thumb) |
| Catálogo estático | `routes.py` o nuevo `export_catalog.py`, nueva plantilla `catalogo.html` |


---

## 7. MÓDULO DE EGRESOS / GASTOS (CRÍTICO PARA P&L REAL)

### Contexto y Problema
El sistema actual calcula "ganancia" restando solo los costos de producción teóricos (filamento usado, electricidad, depreciación, labor). Pero **no registra los egresos reales de caja**: compras de rollos nuevos, accesorios no imprimibles (argollas para llaveros, imanes, packaging, cajas, bolsas, tornillos), herramientas, envíos de proveedores, etc.

Sin esto, el balance mensual es incorrecto: puede mostrar ganancia cuando en realidad se gastó más de lo que ingresó.

---

### Modelo de Datos Propuesto

#### Nueva Tabla `Expense` (Egresos / Gastos)
```
id               Integer, PK
date             DateTime, default=now
category         String(50)   — ver categorías abajo
description      String(200)  — ej. "Compra 2 rollos PLA negro Grilon3"
amount           Float        — monto total del gasto ($)
supplier_id      Integer, FK -> Supplier, nullable=True  — si aplica
material_id      Integer, FK -> Material, nullable=True  — si el gasto cargó stock
receipt_url      String(500)  — URL de foto del ticket/factura (mismo approach que image_url)
notes            Text, nullable=True
```

#### Categorías sugeridas (campo `category`):
- `'Filamento'` — compra de rollos
- `'Accesorio'` — argollas, imanes, tornillos, insertos, etc.
- `'Packaging'` — cajas, bolsas, papel tissue, stickers
- `'Herramienta'` — espátulas, alicates, lija, pintura
- `'Mantenimiento'` — ya existe en MaintenanceLog pero puede cruzarse
- `'Envío'` — flete de proveedor
- `'Servicio'` — electricidad, internet, suscripciones
- `'Otro'`

---

### Lógica de Negocio

**Relación con Material:**
Cuando `category = 'Filamento'` y se asocia un `material_id`, el gasto está vinculado a una compra de stock. Esto permite:
- Cruzar "cuánto pagué realmente por este rollo" vs `Material.purchase_cost`
- Trazabilidad: cada rollo tiene su egreso de caja asociado

**Impacto en P&L mensual:**
```
Ganancia Real del Mes =
    Ingresos (Order.total_amount_billed)
  - Costos de Producción Teóricos (snapshot de OrderItems)
  - Comisiones de Plataforma (platform_fee)
  - Egresos Reales del Mes (Expense.amount donde date en rango)
  - Costos de Mantenimiento (MaintenanceLog.cost donde date en rango)
```

**Vista en Dashboard:**
- Nueva KPI box (o expandir la existente de ganancia):
  - "Egresos del mes": suma de todos los `Expense.amount` del mes en curso
  - "Ganancia Real": ingresos - costos producción - comisiones - egresos - mantenimiento
- Gráfico nuevo o ampliado: barras apiladas con desglose de egresos por categoría

---

### Pantalla de Egresos (`/expenses`)

**Vista principal:**
- Tabla con DataTables: fecha, categoría (badge de color), descripción, proveedor, monto
- Filtros: por categoría, por rango de fechas, por proveedor
- Totales al pie: suma del período filtrado
- Botón: "+ Registrar Egreso"

**Formulario "Registrar Egreso":**
- Fecha (default: hoy)
- Categoría (dropdown con las categorías de arriba)
- Descripción (texto libre)
- Monto ($)
- Proveedor (dropdown opcional, los mismos de la tabla `Supplier`)
- Material asociado (dropdown opcional, solo si categoría = Filamento)
- URL de comprobante (campo texto, para foto de ticket subida a nube)
- Notas adicionales

---

### Endpoints API a Crear

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/expenses` | Vista HTML de egresos |
| GET | `/api/expenses` | Lista JSON con filtros opcionales |
| POST | `/api/expenses/create` | Registrar nuevo egreso |
| GET | `/api/expenses/summary` | Resumen por categoría del mes actual |

---

### Archivos a Modificar / Crear

| Archivo | Cambio |
|---|---|
| `models.py` | Nueva clase `Expense` |
| `routes.py` | 4 nuevos endpoints + actualizar cálculo P&L en `/api/kpis` |
| `templates/expenses.html` | Nueva vista completa |
| `templates/layout.html` | Agregar ítem "Expenses" al menú lateral |
| `templates/dashboard.html` | Actualizar KPI de ganancia + nuevo dato de egresos |