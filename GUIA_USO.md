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

## 🆕 Funciones Nuevas

### Seguimiento de pedidos (link público)
Cada pedido hecho desde `/catalogo` genera automáticamente un link único tipo
`/seguimiento/CODIGO123` que el cliente recibe apenas hace el pedido (con botón
para copiarlo o mandárselo por WhatsApp). Desde `/customer-orders` (panel admin)
podés ir cambiando el estado del pedido con un selector: **Recibido → En cola →
Imprimiendo → Listo para retirar → Entregado**. El cliente ve ese progreso en
tiempo real entrando a su link, sin tener que preguntarte por WhatsApp.

### Cotización de piezas a medida
En `/cotizar` (con un botón visible en el catálogo: "¿No lo encontrás? Pedí un
presupuesto a medida") el cliente puede describir una pieza que no está en el
catálogo y, opcionalmente, subir un archivo (STL, OBJ, 3MF, STEP, foto o PDF,
hasta 20MB) o pegar un link de Drive de referencia. Te llega un aviso a Telegram
con los datos y, si subió un archivo, **el archivo llega directo adjunto al
mensaje de Telegram**. Gestionás las solicitudes desde `/cotizaciones` en el panel
(cambiar estado, descargar el archivo, contactar por WhatsApp con un clic).

### Backup automático de la base de datos por email
En `/config`, sección "Backup automático de la base de datos", cargás:
1. El email donde querés recibir el backup.
2. Una cuenta de Gmail remitente.
3. Una **contraseña de aplicación** de esa cuenta de Gmail (no la contraseña
   normal — se genera en https://myaccount.google.com/apppasswords, requiere
   tener la verificación en 2 pasos activada).
4. Activás el interruptor y probás con el botón "Enviar backup de prueba ahora".

Para que se envíe solo (por ejemplo, una vez por semana) sin que tengas que
apretar el botón, hay que programarlo **una vez** desde PythonAnywhere:
1. Entrá a tu cuenta de PythonAnywhere → pestaña **Tasks**.
2. En "Scheduled task", elegí un horario semanal (ej: todos los lunes 6:00 AM).
3. En el comando, poné: `python3 /home/TU_USUARIO/3dmaker/backup.py`
   (reemplazá `TU_USUARIO` y la ruta según donde esté tu proyecto).
4. Guardá. A partir de ahí corre solo, según lo que hayas activado en `/config`.

Si tu plan de PythonAnywhere no tiene la pestaña Tasks disponible (algunos
planes gratuitos limitan esto), el botón manual de "Enviar backup de prueba
ahora" siempre te sirve para hacerlo a mano cuando quieras.

### SEO y vista previa al compartir
El catálogo ahora tiene meta tags Open Graph: al compartir el link de
`/catalogo` por WhatsApp o Instagram se va a ver una tarjeta con el nombre,
descripción e imagen del taller (usando el logo configurado en `/config`, o si
no la primera foto de producto disponible). También se agregó `/robots.txt` y
`/sitemap.xml` para que Google pueda indexar el catálogo.

### Protección anti-spam
Los formularios públicos (pedido y cotización) tienen un campo trampa invisible
que descarta envíos de bots automáticos, y un límite de intentos por hora por
dirección IP para evitar abuso. El login del panel también tiene un límite de
intentos para dificultar ataques de fuerza bruta.

## 📈 Próximos Pasos Recomendados

1. **Integrar Mercado Pago**: pagos automáticos desde el catálogo (pendiente:
   requiere monotributo habilitado, según lo conversado).
2. **Uber Direct / delivery a domicilio**: quedó en veremos — la disponibilidad
   en Argentina no está confirmada y depende de tener antes una pasarela de pago.
3. **App móvil**: versión nativa para smartphone (hoy ya es usable desde el
   navegador del celular, incluida la carga rápida de productos).
4. **Reseñas de clientes** y sección "Cómo trabajo" en el catálogo, para sumar
   confianza.

## 📞 Soporte

Consulta los comentarios en:
- `models.py` - Estructura de datos
- `routes.py` - Endpoints y lógica
- `templates/` - Estructura del frontend

---

**Version:** 1.0  
**Última actualización:** 2026-05-29  
**Estado:** ✅ Production Ready (con ajustes de seguridad)
