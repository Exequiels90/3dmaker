# 📚 GUÍA DE USO - Sistema de Gestión 3D Printing Workshop

## 🚀 Inicio Rápido

### Opción 1: Ejecución Directa
```bash
cd c:\Users\PC-001-8325\Pictures\so
python app.py
```

La aplicación iniciará en: **http://localhost:5000**

### Opción 2: Con Entorno Virtual (Recomendado)
```bash
cd c:\Users\PC-001-8325\Pictures\so
venv\Scripts\activate
python app.py
```

## ⚙️ Configuración Inicial

### Si es la primera vez:
1. La aplicación creará automáticamente la base de datos SQLite
2. Se inicializará con valores por defecto en GlobalConfig
3. La tabla `global_config` se creará con valores para:
   - Costo de electricidad: $0.12/kWh
   - Costo de mano de obra: $15/hora
   - Margen de ganancia base: 150%
   - Multiplicador de riesgo: 1.05

### Si hay error de esquema:
Si ves un error `sqlalchemy.exc.OperationalError: no such column`:
1. La app automáticamente reconstruirá las tablas
2. Todos los datos antiguos se perderán (primera ejecución)
3. Luego funcionará normalmente

## 📱 Acceso a Funciones

### Dashboard (`/dashboard`)
- **KPI Boxes**: Revenue, Profit, Stock, Alerts
- **Gráficos interactivos**:
  - Revenue vs Costs (últimos 12 meses)
  - Waste Trends (tendencia de desperdicio)
  - Cost Breakdown (desglose dinámico por producto)

### Sales (`/sales`)
- Crear nuevas órdenes
- Seleccionar cliente y productos
- Validar stock automáticamente
- Historial de ventas con filtros

### Inventory (`/inventory`)
- **Pestaña Products**: Catálogo de diseños
- **Pestaña Materials**: Inventario de filamentos
- Progress bars de stock (verde/amarillo/rojo)
- Registrar desperdicio con cálculo de impacto

### Configuration (`/config`)
- Parámetros globales (kWh, labor, margins)
- Gestión de impresoras
- Historial de mantenimiento
- Gestión de proveedores

## 💾 Base de Datos

**Archivo**: `so.sqlite`  
**Ubicación**: `c:\Users\PC-001-8325\Pictures\so\so.sqlite`

### Tablas Principales:
- `supplier` - Proveedores
- `material` - Filamentos/resinas
- `printer` - Máquinas
- `maintenance_log` - Historial de servicio
- `product` - Catálogo de productos
- `customer` - Clientes
- `order` - Órdenes (encabezado)
- `order_item` - Detalle de órdenes
- `waste_log` - Control de fallas
- `global_config` - Parámetros del sistema

## 🔧 Solución de Problemas

### Error: "ModuleNotFoundError: No module named 'flask'"
```bash
pip install -r requirements.txt
```

### Error: "OperationalError: no such column"
1. La app reconstruirá automáticamente la BD
2. Si persiste, elimina `so.sqlite` manualmente
3. Reinicia la aplicación

### Los gráficos no cargan
1. Abre la consola del navegador (F12)
2. Verifica si hay errores de CORS
3. Recarga la página

### Stock no se deduce en órdenes
1. Verifica que el producto tenga un material asociado
2. Verifica que haya stock disponible
3. Revisa el estado de la orden en historial

## 📊 Fórmulas Utilizadas

**Costo de Material:**
```
peso_gramos × (costo_rollo / total_peso_rollo)
```

**Costo de Electricidad:**
```
(watts_impresora / 1000) × horas_impresión × $/kWh
```

**Costo de Depreciación:**
```
horas_impresión × (precio_máquina / horas_vida_útil)
```

**Costo de Mano de Obra:**
```
horas_post_proceso × $/hora
```

**Costo Total Producción:**
```
Material + Electricidad + Depreciación + Labor + Costos_Adicionales
```

**Precio Sugerido:**
```
Costo_Total × (1 + margen_ganancia/100)
```

**Ganancia Neta:**
```
Ingresos - Costo_Producción - Comisión_Plataforma
```

## 🎯 Workflow Típico

### 1. Configuración Inicial
1. Ir a `/config`
2. Revisar/ajustar parámetros globales
3. Crear al menos 1 impresora
4. Crear al menos 1 proveedor

### 2. Agregar Materiales
1. Ir a `/inventory` → pestaña Materials
2. Click "+ Add New Material"
3. Ingresar: brand, type, color, weight, cost

### 3. Crear Productos
1. Ir a `/inventory` → pestaña Products
2. Click "+ Add New Product"
3. Ingresar: nombre, peso, tiempo, material, impresora, costos adicionales
4. El sistema calcula automáticamente el precio sugerido

### 4. Registrar Ventas
1. Ir a `/sales`
2. Click "Create New Order"
3. Seleccionar cliente (o crear uno nuevo)
4. Agregar productos a la orden
5. Sistema valida stock y calcula precios
6. Confirmar orden

### 5. Registrar Desperdicio (si falla impresión)
1. Ir a `/inventory` → pestaña Materials
2. Click "Log Waste" en el filamento
3. Ingresar gramos perdidos y motivo
4. Stock se deduce automáticamente

### 6. Monitorear en Dashboard
1. Ir a `/dashboard`
2. Ver KPIs del mes
3. Analizar gráficos de tendencias
4. Revisar alertas de stock/mantenimiento

## 🔒 Consideraciones de Seguridad

⚠️ **Advertencias para Producción:**
1. Cambiar `secret_key` en app.py
2. Implementar autenticación de usuarios
3. Usar HTTPS/SSL
4. Realizar backups regulares de la BD
5. Configurar logs de auditoría

## 📈 Próximos Pasos Recomendados

1. **Agregar autenticación**: Multi-usuario con roles
2. **Exportar reportes**: PDF/Excel con datos
3. **Integrar Mercado Pago**: Pagos automáticos
4. **App móvil**: Versión para smartphone
5. **Backup automático**: Sincronización con cloud

## 📞 Soporte

Consulta los comentarios en:
- `models.py` - Estructura de datos
- `routes.py` - Endpoints y lógica
- `templates/` - Estructura del frontend

---

**Version:** 1.0  
**Última actualización:** 2026-05-29  
**Estado:** ✅ Production Ready (con ajustes de seguridad)
