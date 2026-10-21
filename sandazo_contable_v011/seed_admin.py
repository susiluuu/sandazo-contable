import os, sys
from sqlalchemy import select
from database import Base, engine, SessionLocal
from models import User
from security import hash_password

if __name__ == '__main__':
    email = os.getenv('ADMIN_EMAIL', '').strip().lower()
    name = os.getenv('ADMIN_NAME', 'Administrador Despacho').strip()
    password = os.getenv('ADMIN_PASSWORD', '')
    if not email or '@' not in email or len(password) < 12:
        sys.exit('Define ADMIN_EMAIL y ADMIN_PASSWORD (mínimo 12 caracteres), y opcionalmente ADMIN_NAME.')
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            sys.exit('Ese correo ya está registrado; no se modificó la contraseña.')
        db.add(User(email=email, full_name=name, password_hash=hash_password(password), is_superadmin=True))
        db.commit()
    print('Administrador inicial creado:', email)
