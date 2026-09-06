"""Extensiones compartidas entre app.py y routes.py (evita imports circulares)."""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Límites por defecto generosos; los endpoints públicos sensibles a spam
# (crear pedido, crear cotización, login) tienen límites más estrictos
# aplicados directamente sobre esas rutas.
limiter = Limiter(key_func=get_remote_address, default_limits=[])
