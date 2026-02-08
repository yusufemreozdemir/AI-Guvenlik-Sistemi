from fastapi import FastAPI, Depends 
from fastapi.middleware.cors import CORSMiddleware 
from contextlib import asynccontextmanager
from database import init_db, SessionLocal, Role, User, AccessLog 
from sqlalchemy.orm import Session 
from passlib.context import CryptContext
from routes import router as api_router
import uvicorn

pwd_context = CryptContext(schemes = ["bcrypt"], deprecated = "auto") # Şifreleme

def create_core_system_data(db):
    """
    Başlangıç verilerini ekler.
    """
    # Rolleri oluştur
    if db.query(Role).count() == 0:
        roles = [
            Role(name = "Admin", description = "Sistem Yöneticisi"),
            Role(name = "Resident", description = "Site Sakini"),
            Role(name = "Security", description = "Güvenlik Görevlisi")
        ]
        db.add_all(roles)
        db.commit()
        print("Roller oluşturuldu.")

    # Admin
    if db.query(User).filter(User.username == "admin").first() is None:
        admin_role = db.query(Role).filter(Role.name == "Admin").first()
        raw_pw = "1234"
        hashed_pw = pwd_context.hash(raw_pw) # admin şifresi
        
        admin_user = User(
            username = "admin",
            password_hash = hashed_pw,
            role_id = admin_role.id
        )
        db.add(admin_user)
        db.commit()
        print(f"Admin oluşturuldu -> User: admin | Password: {raw_pw}")

    # 3. SECURITY KULLANICI
    if db.query(User).filter(User.username == "security").first() is None:
        sec_role = db.query(Role).filter(Role.name == "Security").first()
        raw_pw = "1234"
        hashed_pw = pwd_context.hash(raw_pw) 
        
        sec_user = User(
            username = "security",
            password_hash = hashed_pw,
            role_id = sec_role.id
        )
        db.add(sec_user)
        db.commit()
        print(f"Güvenlik oluşturuldu -> User: security | Password: {raw_pw}")

def create_test_data(db):
    """
    Test amaçlı kullanıcıları ekler.
    """
    # Site sakini (örneğin daire5)
    if db.query(User).filter(User.username == "daire5").first() is None:
        resident_role = db.query(Role).filter(Role.name == "Resident").first()
        raw_pw = "1234"
        hashed_pw = pwd_context.hash(raw_pw) 
        
        resident_user = User(
            username = "daire5", 
            password_hash = hashed_pw, 
            role_id = resident_role.id
        )

        db.add(resident_user)
        db.commit()
        print(f"Site sakini oluşturuldu -> User: daire5 | Password: {raw_pw}")

def create_initial_data():
    """
    Tüm başlangıç verilerini tetikleyen ana fonksiyon.
    """
    db = SessionLocal()
    try:
        create_core_system_data(db) # Zorunlu başlangıç verileri
        create_test_data(db) # Test verileri
             
    except Exception as e:
        print(f"HATA: Başlangıç verileri hatası: {e}")
    finally:
        db.close()

# Lifespan döngüsü
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Uygulama başlarken çalışacak kodlar
    print("Sistem Başlatılıyor")
    init_db()
    create_initial_data()
    print("Sistem Hazır ve Çalışıyor")
    
    yield 
    print("Sistem Kapatılıyor")

app = FastAPI(title = "AI Guvenlik Sistemi (MVP)", lifespan = lifespan) # FastAPI uygulamasını lifespan ile başlat

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"], 
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

app.include_router(api_router)

def get_db():
    db = SessionLocal()
    yield db
    db.close()

@app.get("/latest-log")
def get_latest_log(db: Session = Depends(get_db)):

    last_log = db.query(AccessLog).order_by(AccessLog.timestamp.desc()).first() # Tarihe göre tersten sırala ve ilkini al
    
    if last_log:
        return {
            "plate": last_log.plate_number,
            "status": last_log.access_status, 
            "owner": "Bilinmiyor", 
            "time": last_log.timestamp.strftime("%H:%M:%S")
        }
    return {"plate": "-", "status": False, "owner": "-", "time": "-"}

@app.get("/")
def read_root():
    return {"durum": "aktif", "mesaj": "Guvenlik Sistemi Calisiyor"}

if __name__ == "__main__":
    uvicorn.run("app:app", host = "0.0.0.0", port = 8000, reload = True)