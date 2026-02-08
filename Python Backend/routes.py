from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from ai import AccessControlSystem
from database import AccessLog
from database import get_db, User, Role, AllowedPlate

router = APIRouter()

# Ayarlar
SECRET_KEY = "tahmin edilmesi zor bir string" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# --- 1. VERİ ŞEMALARI (Pydantic Models) ---
# Gelen ve giden verinin kuralları burada belirlenir
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class PlateCreate(BaseModel):
    plate_number: str

class PlateResponse(BaseModel):
    id: int
    plate_number: str
    created_at: datetime
    user_id: int
    
    class Config:
        from_attributes = True

class AdminLogResponse(BaseModel):
    id: int
    plate_number: str
    access_status: bool
    vlm_description: str
    timestamp: datetime
    related_user: Optional[str] = "Bilinmiyor" # İlişkili kullanıcı adı

class AdminPlateResponse(BaseModel):
    id: int
    plate_number: str
    created_at: datetime
    owner_username: str # Plakayı ekleyen kişi

# --- 2. YARDIMCI FONKSİYONLAR ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm = ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Gelen istekteki Token'ı kontrol eder, geçerliyse kullanıcıyı bulur.
    """
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail = "Gecersiz kimlik bilgisi",
        headers = {"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# API uçları
@router.post("/login", response_model = Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Kullanici adi veya sifre hatali",
            headers = {"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data = {"sub": user.username, "role": user.role_id})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "role": user.role.name 
    }

@router.get("/users/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Şu an giriş yapmış olan kullanıcının bilgilerini döner.
    """
    return {"username": current_user.username, "role_id": current_user.role_id}

@router.post("/plates/", response_model=PlateResponse)
def add_plate(plate: PlateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Yeni plaka ekler. (Sadece giriş yapmış kullanıcı ekleyebilir)
    """

    clean_plate = plate.plate_number.upper().replace(" ", "") # Plakayı büyük harfe çevirip boşlukları sil
    
    # Aynı plaka daha önce eklenmiş mi?
    existing_plate = db.query(AllowedPlate).filter(AllowedPlate.plate_number == clean_plate).first()
    if existing_plate:
         raise HTTPException(status_code = 400, detail = "Bu plaka zaten sistemde kayıtlı.")

    new_plate = AllowedPlate(
        plate_number = clean_plate,
        user_id = current_user.id
    )

    db.add(new_plate)
    db.commit()
    db.refresh(new_plate)
    return new_plate

@router.get("/plates/", response_model =List[PlateResponse])
def read_plates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Plakaları listeler.
    Görüntüleyen kişi admin ya da güvenlik ise bütün plakaları görür, site sakini ise sadece kendi eklediği plakaları görür.
    """
    # Kullanıcının rolünü bul
    role_name = current_user.role.name
    
    if role_name == "Admin" or role_name == "Security":
        return db.query(AllowedPlate).all()
    else:
        return db.query(AllowedPlate).filter(AllowedPlate.user_id == current_user.id).all()

try:
    ai_system = AccessControlSystem()
except Exception as e:
    print(f"AI Sistem başlatılamadı: {e}")
    ai_system = None

@router.get("/video_feed")
def video_feed():
    """
    Tarayıcıda canlı yayın izlemek için endpoint.
    """
    if ai_system is None:
        return {"error": "AI Sistemi aktif degil"}

    return StreamingResponse(ai_system.generate_frames(), media_type = "multipart/x-mixed-replace; boundary=frame")

@router.get("/admin/logs", response_model = List[AdminLogResponse])
def get_all_logs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Tüm geçiş loglarını getirir. Sadece Admin ve Security yetkisi olanlar görebilir.
    """
    if current_user.role.name not in ["Admin", "Security"]:
        raise HTTPException(status_code = 403, detail = "Yetkiniz yok")

    logs = db.query(AccessLog).order_by(AccessLog.timestamp.desc()).all()
    
    response_data = []
    for log in logs:
        user_name = "Misafir/Tanımsız"
        if log.related_user_id:
            user = db.query(User).filter(User.id == log.related_user_id).first()
            if user:
                user_name = user.username
        
        response_data.append(AdminLogResponse(
            id = log.id,
            plate_number = log.plate_number,
            access_status = log.access_status,
            vlm_description = log.vlm_description,
            timestamp = log.timestamp,
            related_user = user_name
        ))
        
    return response_data

@router.get("/admin/plates", response_model = List[AdminPlateResponse])
def get_all_plates_detail(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Tüm plakaları ve sahiplerni getirir.
    """
    if current_user.role.name not in ["Admin", "Security"]:
        raise HTTPException(status_code =403, detail = "Yetkiniz yok")

    plates = db.query(AllowedPlate).all()
    
    response_data = []
    for plate in plates:
        owner = db.query(User).filter(User.id == plate.user_id).first()
        owner_name = owner.username if owner else "Silinmiş Kullanıcı"
        
        response_data.append(AdminPlateResponse(
            id = plate.id,
            plate_number = plate.plate_number,
            created_at = plate.created_at,
            owner_username = owner_name
        ))
        
    return response_data