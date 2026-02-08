import cv2
import torch
import time
import os
import re
from datetime import datetime
from collections import Counter, deque
from ultralytics import YOLO
from PIL import Image 
import google.generativeai as genai 

from database import SessionLocal, AllowedPlate, AccessLog, User # Veritabanı bağlantıları

OCR_TYPE = "Easy" # varsayılanOCR modeli seçimi
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"

GEMINI_API_KEY = "Gemini_api_key"

try:
    genai.configure(api_key = GEMINI_API_KEY)
    vlm_model = genai.GenerativeModel('gemini-2.5-flash')
    VLM_ACTIVE = True

except Exception as e:
    print(f"Gemini API başlatılamadı: {e}")
    VLM_ACTIVE = False

print(f"Seçilen OCR Motoru: {OCR_TYPE}")
print(f"VLM Durumu: {"Aktif" if VLM_ACTIVE else "Pasif"}")

# Rapid seçildiyse
if OCR_TYPE == "Rapid":
    from rapidocr_onnxruntime import RapidOCR

# easyocr seçildiyse
elif OCR_TYPE == "Easy":
    import easyocr

class AccessControlSystem:

    def __init__(self, vehicle_weights = "weights/yolo26m.pt", plate_weights = "weights/best_plate.pt", use_gpu = True):

        print("\nSistem başlatılıyor... ")
        
        self.device = "cuda" if torch.cuda.is_available() and use_gpu else "cpu"
        print(f"Donanım: {self.device.upper()}")

        if not os.path.exists("weights"):
            os.makedirs("weights")

        # Araç tespit modeli
        print(f"Araç modeli yükleniyor...")
        self.vehicle_model = YOLO(vehicle_weights) 

        # Plaka tespit modeli
        print(f"Plaka Modeli Yükleniyor...")
        self.plate_model = YOLO(plate_weights)

        # OCR modeli
        print(f"OCR Başlatılıyor... ({OCR_TYPE})")

        if OCR_TYPE == "Rapid":
            self.reader = RapidOCR()
        else:
            self.reader = easyocr.Reader(["en"], gpu = (self.device == "cuda"))

        self.vehicle_classes = [2, 3, 5, 7] 
        self.plate_history = deque(maxlen = 20) 
        self.stable_plate = None              
        self.mismatch_count = 0               
        self.last_read_time = time.time()     

        self.cooldown_tracker = {} 
        self.cooldown_seconds = 10.0
        self.frame_count = 0

    # Tespit edilen plakada regex temizliği 
    def clean_plate_text(self, text):
        if not text: return None
        clean_text = re.sub(r"[^A-Z0-9]", "", text.upper())

        if re.match(r'^\d{2}[A-Z]{1,3}\d{2,5}$', clean_text): #2 nümerik - 1-3 alfabetik - 2-5 nümerik karakter
            return clean_text
        
        return None

    def get_best_plate(self):
        if not self.plate_history: return None
        most_common = Counter(self.plate_history).most_common(1)
        plate, count = most_common[0]
        if count > 2: return plate 
        return None

    def perform_ocr(self, plate_crop):
        raw_text = ""
        try:
            if OCR_TYPE == "Rapid":
                result, _ = self.reader(plate_crop)
                if result:
                    raw_text = result[0][1]
            else:
                results = self.reader.readtext(plate_crop, detail = 0)
                if results:
                    raw_text = "".join(results)

            return self.clean_plate_text(raw_text)
        
        except:
            return None

    def get_vehicle_description(self, vehicle_img_array):
        """
        Kırpılmış araç görüntüsünü VLM'e gönderir ve yorum alır.
        """
        if not VLM_ACTIVE:
            return "VLM Kapalı"
        
        try:
            rgb_img = cv2.cvtColor(vehicle_img_array, cv2.COLOR_BGR2RGB) # BGR - RGB dönüşümü
            pil_img = Image.fromarray(rgb_img) # Numpy Array - PIL Image
            
            prompt = """
            Bu aracı kısaca tanımla. Sadece Marka, Model (tahmini), Renk ve Kasa Tipi (Sedan/Hatchback/SUV/Kamyon) bilgisini Türkçe olarak, 
            virgülle ayırarak kısaca yaz. 
            Örnek: Beyaz, Toyota Corolla, Sedan.
            """
            response = vlm_model.generate_content([prompt, pil_img])
            return response.text.strip()
        except Exception as e:
            print(f"VLM Analizinde Hata: {e}")
            return "Tanımlanamadı"

    def check_database(self, plate_text, vlm_desc):
        """Veritabanı sorgusu yapar ve log yazar."""
        db = SessionLocal()
        try:
            allowed = db.query(AllowedPlate).filter(AllowedPlate.plate_number == plate_text).first() # İzin kontrolü
            
            access_status = False
            owner_name = "Misafir"
            user_id = None
            
            if allowed:
                access_status = True
                user_id = allowed.user_id
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    owner_name = user.username

            # Loglama 
            new_log = AccessLog(
                plate_number = plate_text,
                access_status = access_status,
                vlm_description = vlm_desc,
                related_user_id = user_id,
                timestamp = datetime.now()
            )
            db.add(new_log)
            db.commit()
            
            return access_status, owner_name
            
        except Exception as e:
            print(f"Veritabanı Hatası: {e}")
            return False, "HATA"
        
        finally:
            db.close()

    def process_frame(self, frame):
        self.frame_count += 1
        
        # 3 saniye boyunca araç tespit edilmezse hafıza sıfırlansın
        if time.time() - self.last_read_time > 3.0:
            if self.stable_plate:
                self.plate_history.clear()
                self.stable_plate = None
                self.mismatch_count = 0

        # yolo26m (Araç tespiti ve kırpma)
        results = self.vehicle_model(frame, classes = self.vehicle_classes, conf = 0.5, verbose = False, device = self.device)[0]
        
        best_vehicle_box = None
        max_vehicle_area = 0

        for box in results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            area = (x2 - x1) * (y2 - y1)
            if area > max_vehicle_area:
                max_vehicle_area = area
                best_vehicle_box = (x1, y1, x2, y2)

        if best_vehicle_box and max_vehicle_area > 5000:
            vx1, vy1, vx2, vy2 = best_vehicle_box
            vehicle_crop = frame[vy1:vy2, vx1:vx2] # Araç görüntüsünü kırp

            cv2.rectangle(frame, (vx1, vy1), (vx2, vy2), (255, 255, 0), 2)

            # yolo26s (Plaka tespiti, yolo26m tarafından kırpılmış araç görüntüsünü alır.)
            plate_results = self.plate_model(vehicle_crop, conf = 0.2, verbose = False, device = self.device)[0]
            
            best_plate_box = None
            max_plate_area = 0

            for p_box in plate_results.boxes:
                px1, py1, px2, py2 = map(int, p_box.xyxy[0])
                p_area = (px2 - px1) * (py2 - py1)

                if p_area > max_plate_area:
                    max_plate_area = p_area
                    best_plate_box = (px1, py1, px2, py2) # Plaka görüntüsünü kırp

            if best_plate_box:
                self.last_read_time = time.time()
                px1, py1, px2, py2 = best_plate_box
                
                # OCR (Plaka okuma, yolo26s tarafından kırpılmış plaka görüntüsünü alır.)
                if self.frame_count % 3 == 0:
                    plate_img = vehicle_crop[py1:py2, px1:px2]
                    final_text = self.perform_ocr(plate_img)

                    if final_text:
                        if self.stable_plate and final_text != self.stable_plate:
                            self.mismatch_count += 1
                            if self.mismatch_count >= 3:
                                self.plate_history.clear()
                                self.plate_history.append(final_text)
                                self.stable_plate = final_text
                                self.mismatch_count = 0
                        else:
                            self.mismatch_count = 0
                            self.plate_history.append(final_text)

                current_best = self.get_best_plate() # Kararlı plakayı belirle
                
                if current_best:
                    self.stable_plate = current_best
                    
                    g_px1, g_py1 = vx1 + px1, vy1 + py1
                    g_px2, g_py2 = vx1 + px2, vy1 + py2
                    
                    current_time = time.time()
                    last_check = self.cooldown_tracker.get(current_best, 0)
                    
                    color = (0, 255, 255) 
                    info_text = f"{current_best}"

                    # Veritabanı kaydı ve VLM çağrısı
                    if current_time - last_check > self.cooldown_seconds:
                        print(f"Araç analizi yapılıyor... ({current_best})")
                        
                        # VLM çağrısı
                        vehicle_desc = self.get_vehicle_description(vehicle_crop)
                        print(f"Sonuç: {vehicle_desc}")

                        
                        self.check_database(current_best, vehicle_desc) # Veritabanına kaydet
                        self.cooldown_tracker[current_best] = current_time
                    
                    cv2.rectangle(frame, (g_px1, g_py1), (g_px2, g_py2), color, 2)
                    cv2.putText(frame, info_text, (g_px1, g_py1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        return frame

    def generate_frames(self):
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        while True:
            success, frame = cap.read()
            if not success:
                break
            
            processed_frame = self.process_frame(frame)
            _, buffer = cv2.imencode(".jpg", processed_frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# Test kodu
if __name__ == "__main__":
    print("CANLI KAMERA TEST")
    v_path = "weights/yolo26m.pt" 
    p_path = "weights/final_plaka_modeli.pt"

    try:
        system = AccessControlSystem(v_path, p_path)
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        print("Kamera açıldı. Çıkış için 'q' basın.")
        
        prev_time = 0

        # Ana çalışma döngüsü
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if prev_time > 0 else 0
            prev_time = curr_time

            frame = system.process_frame(frame)
            
            cv2.putText(frame, f"FPS: {int(fps)}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.imshow("AI Test", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
    except Exception as e:
        print(f"HATA: {e}")