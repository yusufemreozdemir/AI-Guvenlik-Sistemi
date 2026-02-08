from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import datetime

DATABASE_URL = "sqlite:///./guvenlik.db"

engine = create_engine(DATABASE_URL, connect_args = {"check_same_thread": False}) # Veritabanı motorunu oluştur
SessionLocal = sessionmaker(autocommit = False, autoflush = False, bind = engine) # Oturum oluşturucu
Base = declarative_base() # Tablo modelleri için temel sınıf

# Roller tablosu
class Role(Base):
    __tablename__ = "roles"   
    id = Column(Integer, primary_key = True, index = True)
    name = Column(String, unique = True, index = True)
    description = Column(String, nullable = True)
    users = relationship("User", back_populates = "role")

# Kullanıcı tablosu
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key = True, index = True)
    username = Column(String, unique = True, index = True)
    password_hash = Column(String)
    role_id = Column(Integer, ForeignKey("roles.id"))
    role = relationship("Role", back_populates = "users")
    allowed_plates = relationship("AllowedPlate", back_populates = "owner")

# Geçerli plakalar tablosu
class AllowedPlate(Base):
    __tablename__ = "allowed_plates"
    id = Column(Integer, primary_key = True, index = True)
    plate_number = Column(String, index = True)
    created_at = Column(DateTime, default = datetime.datetime.now)
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates = "allowed_plates")

# Loglar tablosu
class AccessLog(Base):
    __tablename__ = "access_logs"
    id = Column(Integer, primary_key = True, index = True)
    plate_number = Column(String)
    access_status = Column(Boolean)
    vlm_description = Column(String, nullable = True)
    timestamp = Column(DateTime, default = datetime.datetime.now)
    related_user_id = Column(Integer, ForeignKey("users.id"), nullable = True)

def init_db():
    """Tabloları oluşturur."""
    Base.metadata.create_all(bind = engine)
    print("Veritabanı ve tablolar başarıyla oluşturuldu.")

def get_db():
    db = SessionLocal()
    yield db
    db.close()

# Test bloğu
if __name__ == "__main__":
    init_db()