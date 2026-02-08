from ultralytics import YOLO
import torch

# GPU Kontrolü
print(f"GPU Durumu: {torch.cuda.is_available()}")

def convert_to_engine(model_path):
    print(f"{model_path} dönüştürülüyor")
    try:
        model = YOLO(model_path)
        model.export(format = "engine", device = 0, imgsz = 640, dynamic = True) 
        print(f"BAŞARILI: {model_path} -> .engine formatına döndü.")
    except Exception as e:
        print(f"HATA: {e}")

if __name__ == "__main__":
    convert_to_engine("weights/yolo26m.pt") # Araç Modeli 
    convert_to_engine("weights/best_plate.pt") # 1. Plaka modeli
    convert_to_engine("weights/final_plaka_modeli.pt") # 2. Plaka modeli (fine tune ettiğim model)
     