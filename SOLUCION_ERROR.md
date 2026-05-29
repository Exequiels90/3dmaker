🔧 **SOLUCIÓN AL ERROR: "no such column: order.customer_id"**

El error ocurre porque existe una base de datos SQLite antigua con un esquema incompatible.

---

## ✅ **SOLUCIÓN RÁPIDA (3 pasos)**

### Paso 1: DETENER la aplicación
- Presiona **CTRL+C** en la terminal donde está ejecutándose Flask

### Paso 2: LIMPIAR la base de datos
```bash
python cleanup_db.py
```

Esto debería mostrar:
```
========== DATABASE CLEANUP ==========
📦 Found database file: c:\Users\PC-001-8325\Pictures\so\so.sqlite
🔄 Attempting to delete corrupted database...
✅ Database successfully deleted!
```

### Paso 3: REINICIAR la aplicación
```bash
python app.py
```

La primera vez que inicia, debería mostrar:
```
✅ Database initialized successfully!
```

---

## 🎯 **O USAR EL SCRIPT AUTOMÁTICO**

En lugar de ejecutar los comandos manualmente, puedes usar el script batch:

1. Haz doble clic en: **`recreate_db.bat`**
2. Esto automáticamente:
   - Limpia la BD antigua
   - Inicia Flask
   - Recrea la BD con el esquema correcto

---

## 🚀 **SI SIGUE SIN FUNCIONAR**

### Opción A: Eliminar manualmente el archivo
1. Navega a: `c:\Users\PC-001-8325\Pictures\so\`
2. Busca el archivo `so.sqlite`
3. Elimínalo (presiona Delete)
4. Ejecuta: `python app.py`

### Opción B: Usar la variable de entorno
```bash
set FORCE_RESET_DB=true
python app.py
```

### Opción C: Limpiar todo y empezar de cero
```bash
python cleanup_db.py
rm -Force so.sqlite  # Si aún existe
python app.py
```

---

## 📋 **CHECKLIST**

- [ ] Cerré la aplicación Flask (CTRL+C)
- [ ] Ejecuté `python cleanup_db.py`
- [ ] Veo el mensaje "✅ Database successfully deleted!"
- [ ] Ejecuté `python app.py` de nuevo
- [ ] Ahora accedo a http://localhost:5000
- [ ] El dashboard carga sin errores

---

## 💡 **¿QUÉ CAUSÓ EL ERROR?**

La base de datos SQLite original tenía un esquema antiguo sin la columna `customer_id` en la tabla `order`. Al actualizar los modelos, SQLAlchemy espera esta columna pero no existía.

**La solución es simple:** Recrear la BD desde cero con el esquema correcto. Los datos se pierden (si había), pero la estructura ahora será correcta.

---

## ✨ **DESPUÉS DE LIMPIAR**

Una vez que funcione, deberías ver:
- ✅ Dashboard con 4 cajas KPI
- ✅ Acceso a todas las secciones (Sales, Inventory, Configuration)
- ✅ Gráficos interactivos cargando
- ✅ Sin errores de "no such column"

---

**¿Problemas?** Prueba los pasos en orden. El Paso 2 (cleanup) generalmente resuelve todo.
