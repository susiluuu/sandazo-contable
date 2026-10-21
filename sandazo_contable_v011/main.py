import os, re, secrets, csv, io
from datetime import datetime
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from database import Base, engine, SessionLocal
from models import User, Company, Membership, Account, Audit, CompanySettings, Obligation, ReminderEvent
from security import hash_password, verify_password

SECRET = os.getenv('SESSION_SECRET', '')
if len(SECRET) < 32:
    raise RuntimeError('Configura SESSION_SECRET con al menos 32 caracteres aleatorios.')
Base.metadata.create_all(engine)  # V0.1; migraciones formales antes de producción
app = FastAPI(title='Sandazo Contable V0.1.1', docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=SECRET, session_cookie='sandazo_session', same_site='lax', https_only=os.getenv('COOKIE_SECURE','0') == '1', max_age=60*60*8)
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

ROLES = ('admin','contador','consulta')

def redirect(url): return RedirectResponse(url, status_code=303)
def current_user(req, db):
    uid = req.session.get('uid')
    return db.get(User, uid) if uid else None

def login_required(req, db):
    user = current_user(req, db)
    if not user or not user.is_active: raise HTTPException(status_code=401, detail='Inicia sesión')
    return user

def require_csrf(req, token):
    if not token or not secrets.compare_digest(str(req.session.get('csrf','')), token):
        raise HTTPException(status_code=403, detail='Token de seguridad inválido')

def get_role(db, user, company_id):
    if user.is_superadmin: return 'admin'
    return db.scalar(select(Membership.role).where(Membership.user_id==user.id, Membership.company_id==company_id))

def permit(db, user, company_id, allowed=('admin','contador','consulta')):
    company = db.get(Company, company_id)
    if not company or not company.active: raise HTTPException(404, 'Empresa no disponible')
    role = get_role(db, user, company_id)
    if role not in allowed: raise HTTPException(403, 'No tienes permisos para esta empresa')
    return company, role

def render(req, name, **kwargs):
    if not req.session.get('csrf'): req.session['csrf'] = secrets.token_urlsafe(32)
    return templates.TemplateResponse(request=req, name=name, context={'csrf':req.session['csrf'], **kwargs})

def safe_csv(value):
    value = str(value)
    return '\'' + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value

def log(db, user, company_id, action, detail):
    db.add(Audit(actor_user_id=user.id, company_id=company_id, action=action, detail=detail[:500]))

@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, 'login.html', error=None)

@app.post('/login')
def login(request: Request, email: str=Form(...), password: str=Form(...), csrf: str=Form(...)):
    require_csrf(request, csrf)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email==email.strip().lower()))
        if not user or not user.is_active or not verify_password(password, user.password_hash):
            return render(request,'login.html',error='Correo o contraseña incorrectos')
        request.session.clear()
        request.session['uid'] = user.id
        request.session['csrf'] = secrets.token_urlsafe(32)
        return redirect('/')

@app.post('/logout')
def logout(request: Request, csrf: str=Form(...)):
    require_csrf(request, csrf)
    request.session.clear()
    return redirect('/login')

@app.get('/')
def home(request: Request):
    with SessionLocal() as db:
        user = current_user(request, db)
        if not user or not user.is_active: return redirect('/login')
        q = select(Company).order_by(Company.name)
        if not user.is_superadmin:
            q = q.join(Membership).where(Membership.user_id==user.id)
        companies = db.scalars(q).all()
        obligations=db.scalars(select(Obligation)).all() if user.is_superadmin else db.scalars(select(Obligation).where(Obligation.company_id.in_([c.id for c in companies]))).all()
        return render(request,'home.html', user=user, companies=companies, obligations=obligations)

@app.post('/companies')
def create_company(request: Request, name: str=Form(...), rfc: str=Form(...), regime: str=Form(''), fiscal_year: int=Form(2026), csrf: str=Form(...)):
    require_csrf(request, csrf)
    with SessionLocal() as db:
        user=login_required(request, db)
        if not user.is_superadmin: raise HTTPException(403,'Solo administración del despacho')
        rfc=rfc.upper().strip(); name=name.strip()
        if not (12<=len(rfc)<=13 and re.fullmatch(r'[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}',rfc)) or len(name)<3 or not (2000<=fiscal_year<=2100):
            raise HTTPException(422,'Verifica razón social, RFC y ejercicio')
        company=Company(name=name, rfc=rfc, regime=regime[:120], fiscal_year=fiscal_year)
        db.add(company)
        try:
            db.flush()
            log(db,user,company.id,'empresa_creada',name)
            db.commit()
        except IntegrityError:
            db.rollback(); raise HTTPException(409,'Ya existe una empresa con este RFC')
        return redirect(f'/companies/{company.id}')

@app.get('/companies/{cid}')
def company_detail(request: Request, cid: int):
    with SessionLocal() as db:
        user=login_required(request,db)
        company, role=permit(db,user,cid)
        accounts=db.scalars(select(Account).where(Account.company_id==cid).order_by(Account.code)).all()
        members=db.execute(select(Membership,User).join(User,Membership.user_id==User.id).where(Membership.company_id==cid).order_by(User.full_name)).all()
        staff=db.scalars(select(User).where(User.is_active==True).order_by(User.full_name)).all() if role=='admin' else []
        settings=db.get(CompanySettings,cid) or CompanySettings(company_id=cid)
        obligations=db.scalars(select(Obligation).where(Obligation.company_id==cid).order_by(Obligation.due_date,Obligation.id)).all()
        return render(request,'company.html',user=user,company=company,role=role,accounts=accounts,members=members,staff=staff,settings=settings,obligations=obligations)

@app.post('/companies/{cid}/accounts')
def add_account(request: Request,cid:int,code:str=Form(...),name:str=Form(...),nature:str=Form(...),sat_group:str=Form(''),parent_code:str=Form(''),csrf:str=Form(...)):
    require_csrf(request,csrf)
    with SessionLocal() as db:
        user=login_required(request,db); permit(db,user,cid,('admin','contador'))
        code=code.strip();name=name.strip();parent_code=parent_code.strip()
        if not re.fullmatch(r'[A-Za-z0-9.\-]{1,35}',code) or not (2<=len(name)<=200) or nature not in ('deudora','acreedora') or len(sat_group)>25:
            raise HTTPException(422,'Datos de cuenta inválidos')
        parent=None
        if parent_code:
            parent=db.scalar(select(Account).where(Account.company_id==cid,Account.code==parent_code))
            if not parent: raise HTTPException(422,'La cuenta padre no existe en esta empresa')
        account=Account(company_id=cid,code=code,name=name,nature=nature,parent_id=parent.id if parent else None,sat_group=sat_group.strip())
        db.add(account)
        try:
            db.flush();log(db,user,cid,'cuenta_creada',f'{code} {name}');db.commit()
        except IntegrityError:
            db.rollback();raise HTTPException(409,'Ya existe ese código en esta empresa')
    return redirect(f'/companies/{cid}')

@app.get('/companies/{cid}/accounts.csv')
def accounts_csv(request: Request,cid:int):
    with SessionLocal() as db:
        user=login_required(request,db);permit(db,user,cid)
        accounts=db.scalars(select(Account).where(Account.company_id==cid).order_by(Account.code)).all()
        out=io.StringIO();writer=csv.writer(out);writer.writerow(['Código','Cuenta','Naturaleza','Agrupador SAT','Activa'])
        for a in accounts:
            writer.writerow([safe_csv(a.code),safe_csv(a.name),a.nature,safe_csv(a.sat_group),'Sí' if a.active else 'No'])
        data='\ufeff'+out.getvalue()
        return StreamingResponse(iter([data.encode('utf-8')]),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="catalogo_{cid}.csv"'})

@app.post('/users')
def add_user(request:Request,full_name:str=Form(...),email:str=Form(...),password:str=Form(...),csrf:str=Form(...)):
    require_csrf(request,csrf)
    with SessionLocal() as db:
        user=login_required(request,db)
        if not user.is_superadmin: raise HTTPException(403,'Sin permiso')
        full_name=full_name.strip();email=email.lower().strip()
        if len(full_name)<3 or '@' not in email or len(password)<12: raise HTTPException(422,'Nombre, correo o contraseña inválidos (mínimo 12 caracteres)')
        db.add(User(full_name=full_name[:160],email=email,password_hash=hash_password(password)))
        try:
            log(db,user,None,'usuario_creado',email);db.commit()
        except IntegrityError:
            db.rollback();raise HTTPException(409,'Ya existe este correo')
    return redirect('/')

@app.post('/companies/{cid}/members')
def add_member(request:Request,cid:int,user_id:int=Form(...),role:str=Form(...),csrf:str=Form(...)):
    require_csrf(request,csrf)
    with SessionLocal() as db:
        user=login_required(request,db);permit(db,user,cid,('admin',))
        target=db.get(User,user_id)
        if role not in ROLES or not target or not target.is_active: raise HTTPException(422,'Usuario o rol no válido')
        membership=db.scalar(select(Membership).where(Membership.company_id==cid,Membership.user_id==user_id))
        if membership: membership.role=role
        else: db.add(Membership(company_id=cid,user_id=user_id,role=role))
        log(db,user,cid,'permiso_asignado',f'usuario={user_id}, rol={role}');db.commit()
    return redirect(f'/companies/{cid}')

@app.get('/users')
def users_page(request: Request):
    with SessionLocal() as db:
        user=login_required(request,db)
        if not user.is_superadmin: raise HTTPException(403,'Sin permiso')
        staff=db.scalars(select(User).order_by(User.full_name)).all()
        return render(request,'users.html',user=user,staff=staff)

@app.get('/health')
def health():return {'status':'ok','version':'0.1.1'}


# Funciones del despacho (sin envíos externos ni acceso automatizado a portales).
from decimal import Decimal, InvalidOperation
from datetime import date
from pathlib import Path
import uuid
from fastapi import UploadFile, File
from fastapi.responses import FileResponse

STATUS = {'pendiente_presentacion', 'presentada_pendiente_pago', 'pago_reportado', 'pagada_verificada', 'sin_pago', 'cancelada'}
TAXES = {'ISR provisional','IVA','ISR retenido','IVA retenido','Declaración anual','DIOT','Otra obligación'}
UPLOAD_DIR=Path(os.getenv('UPLOAD_DIR','./private_uploads'))
UPLOAD_DIR.mkdir(parents=True,exist_ok=True)

def validate_email(s):
    s=s.strip().lower()
    if s and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',s): raise HTTPException(422,'Correo inválido')
    return s

@app.post('/companies/{cid}/settings')
def save_settings(request: Request,cid:int,csrf:str=Form(...),client_email:str=Form(''),client_phone:str=Form(''),base_currency:str=Form('MXN'),allow_usd:bool=Form(False),sat_opinion:bool=Form(False),imss_opinion:bool=Form(False),infonavit_opinion:bool=Form(False),auto_send_opinions:bool=Form(False),reminders_enabled:bool=Form(False),reminder_whatsapp:bool=Form(False),reminder_email:bool=Form(False)):
    require_csrf(request,csrf)
    with SessionLocal() as db:
        user=login_required(request,db);permit(db,user,cid,('admin','contador'))
        if base_currency not in ('MXN','USD'): raise HTTPException(422,'Moneda inválida')
        if client_phone and not re.fullmatch(r'\+?[0-9 ()-]{10,24}',client_phone): raise HTTPException(422,'Teléfono inválido')
        settings=db.get(CompanySettings,cid)
        if not settings: settings=CompanySettings(company_id=cid);db.add(settings)
        settings.client_email=validate_email(client_email);settings.client_phone=client_phone.strip()
        settings.base_currency=base_currency;settings.allow_usd=allow_usd
        settings.sat_opinion=sat_opinion;settings.imss_opinion=imss_opinion;settings.infonavit_opinion=infonavit_opinion
        settings.auto_send_opinions=auto_send_opinions
        settings.reminders_enabled=reminders_enabled
        settings.reminder_email=reminder_email;settings.reminder_whatsapp=reminder_whatsapp
        log(db,user,cid,'configuracion_cliente','Actualizada; sin activar integraciones externas');db.commit()
    return redirect(f'/companies/{cid}#configuracion')

@app.post('/companies/{cid}/obligations')
def add_obligation(request: Request,cid:int,csrf:str=Form(...),tax_type:str=Form(...),period_year:int=Form(...),period_month:int=Form(...),amount:str=Form(...),due_date:str=Form(...),payment_reference:str=Form(''),notes:str=Form('')):
    require_csrf(request,csrf)
    with SessionLocal() as db:
        user=login_required(request,db);permit(db,user,cid,('admin','contador'))
        if tax_type not in TAXES or not (2000<=period_year<=2100) or not (1<=period_month<=12): raise HTTPException(422,'Periodo o impuesto inválido')
        try:
            val=Decimal(amount)
            if not val.is_finite() or val<0 or val>Decimal('100000000000') or val.as_tuple().exponent < -2: raise ValueError()
            cents=int(val*100)
            date.fromisoformat(due_date)
        except (InvalidOperation,ValueError,OverflowError): raise HTTPException(422,'Importe o fecha inválidos')
        item=Obligation(company_id=cid,tax_type=tax_type,period_year=period_year,period_month=period_month,amount_cents=cents,due_date=due_date,payment_reference=payment_reference[:100],notes=notes[:400])
        db.add(item)
        try:
            db.flush();log(db,user,cid,'obligacion_creada',f'{tax_type} {period_month}/{period_year}');db.commit()
        except IntegrityError:
            db.rollback();raise HTTPException(409,'Ya existe la obligación para ese periodo y versión')
    return redirect(f'/companies/{cid}#obligaciones')

@app.post('/companies/{cid}/obligations/{oid}/status')
def change_obligation(request:Request,cid:int,oid:int,csrf:str=Form(...),status:str=Form(...),paid_at:str=Form(''),submitted_at:str=Form('')):
    require_csrf(request,csrf)
    with SessionLocal() as db:
        user=login_required(request,db);permit(db,user,cid,('admin','contador'))
        item=db.get(Obligation,oid)
        if not item or item.company_id!=cid: raise HTTPException(404,'Obligación no encontrada')
        if status not in STATUS: raise HTTPException(422,'Estado inválido')
        if paid_at:
            try: date.fromisoformat(paid_at)
            except ValueError: raise HTTPException(422,'Fecha de pago inválida')
        if submitted_at:
            try: date.fromisoformat(submitted_at)
            except ValueError: raise HTTPException(422,'Fecha de presentación inválida')
        if status=='pagada_verificada' and not paid_at: raise HTTPException(422,'Para verificar pago registra su fecha y conserva el comprobante en el expediente correspondiente')
        item.status=status;item.paid_at=paid_at if status=='pagada_verificada' else ''
        if submitted_at: item.submitted_at=submitted_at
        log(db,user,cid,'obligacion_estado',f'{oid}: {status}');db.commit()
    return redirect(f'/companies/{cid}#obligaciones')

@app.post('/companies/{cid}/logo')
async def upload_logo(request:Request,cid:int,csrf:str=Form(...),logo:UploadFile=File(...)):
    require_csrf(request,csrf)
    with SessionLocal() as db:
        user=login_required(request,db);permit(db,user,cid,('admin','contador'))
        data=await logo.read(2_000_001)
        if len(data)>2_000_000: raise HTTPException(413,'Tamaño máximo 2MB')
        # No SVG: evita scripts embebidos; verifica formato real por cabecera.
        if data.startswith(b'\x89PNG\r\n\x1a\n'): ext='.png'
        elif data.startswith(b'\xff\xd8\xff'): ext='.jpg'
        else: raise HTTPException(422,'Solo PNG o JPG válidos')
        filename=f'logo_{cid}_{uuid.uuid4().hex}{ext}'
        folder=UPLOAD_DIR/str(cid);folder.mkdir(parents=True,exist_ok=True)
        (folder/filename).write_bytes(data)
        settings=db.get(CompanySettings,cid)
        if not settings: settings=CompanySettings(company_id=cid);db.add(settings)
        old=settings.logo_file;settings.logo_file=filename
        log(db,user,cid,'logo_actualizado',filename);db.commit()
        if old: (folder/old).unlink(missing_ok=True)
    return redirect(f'/companies/{cid}#configuracion')

@app.get('/companies/{cid}/logo')
def view_logo(request:Request,cid:int):
    with SessionLocal() as db:
        user=login_required(request,db);permit(db,user,cid)
        cfg=db.get(CompanySettings,cid)
        if not cfg or not cfg.logo_file: raise HTTPException(404,'Sin logotipo')
        p=UPLOAD_DIR/str(cid)/cfg.logo_file
        if not p.is_file(): raise HTTPException(404,'Archivo no disponible')
        return FileResponse(p,media_type='image/png' if p.suffix=='.png' else 'image/jpeg')
