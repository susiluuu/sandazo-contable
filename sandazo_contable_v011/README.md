# Sandazo Contable V0.1.1 — base web operativa

## Funciona ahora
- Iniciar sesión, crear empresas independientes y asignar usuarios/roles.
- Registrar y exportar catálogo contable por empresa.
- Registrar obligaciones fiscales por empresa, importe, periodo, vencimiento, referencia y estado.
- Distinguir pendiente, presentada, pago reportado y pago verificado (fecha obligatoria).
- Configurar correo, teléfono, monedas, preferencias de opiniones (día 1) y recordatorios (5,3,1,0 días).
- Cargar y consultar logotipo por empresa, protegido por permisos.
- Bitácora de cambios administrativos.

## No está conectado todavía
**No** descarga opiniones ni declaraciones del SAT, IMSS o INFONAVIT; **no** envía emails ni WhatsApp, **no** crea pólizas, no calcula impuestos ni timbra CFDI; **no** consulta el DOF ni almacena e.firma. Estos requieren integraciones y validación en etapas posteriores. Configurar alertas NO significa que ya se ejecuten.

## Ejecutar en computadora (pruebas)
1. Python 3.11+ y entorno virtual.
2. `pip install -r requirements.txt`
3. Configurar `SESSION_SECRET` (mínimo 32 caracteres), opcional `DATABASE_URL`.
4. `python seed_admin.py` siguiendo las instrucciones del archivo (verifica sus variables).
5. `uvicorn main:app --reload` dentro de esta carpeta; abrir http://127.0.0.1:8000.

## Publicación en internet
- Requiere cuenta propia en hosting, PostgreSQL, dominio, HTTPS y almacenamiento persistente privado para logotipos. No se ha desplegado automáticamente.
- Para producción: `DATABASE_URL=postgresql://...`, `SESSION_SECRET` aleatoria fuerte y `COOKIE_SECURE=1` bajo HTTPS.
- Ejecutar `uvicorn main:app --host 0.0.0.0 --port $PORT` como comando inicial en hosting.
- Antes de cargar datos reales: implementar migraciones Alembic, respaldo/restauración, cifrado de archivos en reposo, control de sesiones/rate limiting, seguridad de subida de archivos, almacenamiento persistente, monitoreo y pruebas de autorización. `Base.metadata.create_all` no sustituye migraciones.
- **Nunca publicar el proyecto o su base de datos con credenciales reales en repositorios públicos.**

## Arquitectura futura
- Motor contable: asientos de doble partida, borradores, cierre de periodos, auditoría, reportes por moneda.
- Servicio de TC: Banco de México/DOF con reglas según fecha fiscal aplicable.
- Gestor de CFDI y vault e.firma (sin contraseña en texto plano).
- Trabajos de sincronización con idempotencia y reintentos autorizados.
- Envío de informes y recordatorios con proveedores oficiales y consentimiento.
- Expediente documental, acuses y evidencia de autorización de cliente.

## Archivo `render.yaml`
Incluye una plantilla inicial de Render para el servidor y PostgreSQL. Debe revisarse antes de producción: la carga de logos necesita almacenamiento persistente privado, y hay que añadir migraciones y controles de seguridad. Es una configuración orientativa, **no** un sitio publicado.
