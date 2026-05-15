# JARVIS — Windows AI Asistan

Kişisel yapay zeka asistanı. Gemini Live API ile çalışır.

## Kurulum

### 1. Python Kur
Python 3.11 veya üstü: https://python.org/downloads  
⚠️ Kurulumda **"Add Python to PATH"** kutusunu işaretle!

### 2. Paketleri Kur
```
pip install -r requirements.txt
```

### 3. API Anahtarı Al
https://aistudio.google.com/app/apikey adresine git → **"Create API Key"** → kopyala

### 4. API Anahtarını Gir
`config/api_keys.example.json` dosyasını `config/api_keys.json` olarak kopyala:
```
config/api_keys.example.json  →  config/api_keys.json
```
İçini aç ve anahtarını yapıştır:
```json
{
  "gemini_api_key": "BURAYA_API_ANAHTARINI_YAZ",
  "voice": "Charon",
  "youtube_api_key": "",
  "youtube_channel_handle": ""
}
```

### 5. Başlat
```
python main.py
```

## Özellikler
- Sesli komutlar (Türkçe)
- Uygulama açma/kapatma
- YouTube, Spotify müzik
- Hava durumu
- Sistem bilgisi (CPU, RAM, pil)
- WhatsApp mesaj gönderme
- Takvim ve hatırlatıcılar
- Ekran analizi
