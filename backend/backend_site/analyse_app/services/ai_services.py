import requests
from django.conf import settings

import datetime, os
import environ
import json
from PIL import Image
import requests
from io import BytesIO


from google.cloud import vision
from google import genai
import google.generativeai as generativeai

env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))

GEMINI_API_KEY = env('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError('GEMINI_API_KEY environment variable is not set')



VISION_CLIENT = vision.ImageAnnotatorClient()
generativeai.configure(api_key=GEMINI_API_KEY)


SYSTEM_PROMPT = """
Sen bir toksisite analiz uzmanısın. Kullanıcının gönderdiği ürün ambalajı üzerinde yer alan içerik listesini analiz ederek, ürün içerik bileşenlerinin cilt, solunum, hormon veya genel sağlık açısından toksik olup olmadığını değerlendiriyorsun.

Görevin:
1. İçerikte yer alan zararlı, şüpheli, hormon bozucu, alerjen veya potansiyel olarak toksik maddeleri belirlemek.
2. Kullanıcının **eğer belirttiyse hassasiyetlerine özel** olarak bu maddeler hakkında uyarılarda bulunmak (örneğin: parfüm, alkol, paraben, sülfat, gluten vs.).
3. Genel bir toksisite değerlendirmesi sunmak; sade, anlaşılır ve bilimsel temelli açıklamalar yap.
4. İçeriğin toksisite seviyesini 1 ile 10 arasında bir puanla değerlendir (1: tamamen güvenli, 10: çok toksik).

Cevabını **mutlaka aşağıdaki JSON formatında ve Türkçe olarak** ver:

```json
{
  "genel_aciklama": "Açıklayıcı değerlendirme burada olacak.", 
  "toksisite_skoru": 0-10 arasında bir tam sayı, 
  "tehlikeli_maddeler": ["madde_1", "madde_2", "..."]
}
Kurallar:

* Açıklama Türkçe olmalı.
* "tehlikeli_maddeler" listesi yalnızca gerçekten endişe uyandıran maddeleri içermelidir. Eğer içerik güvenliyse bu liste boş olabilir.
* "toksisite_skoru" mutlaka verilmeli ve ürünün genel güvenliğini sayısal olarak yansıtmalıdır.
* Kullanıcının belirttiği hassasiyetlere mutlaka özel bir dikkat göster.
"""


try:
    GEMINI_MODEL = generativeai.GenerativeModel(
    model_name='gemini-2.0-flash',
    system_instruction=SYSTEM_PROMPT
    )
    GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Gemini modeli yüklenirken hata oluştu: {e}")
    print("Mevcut modelleri ve desteklenen yöntemleri aşağıda listelenmiştir:")
    for m in genai.list_models(): print(m.name)
    exit()


def analyse_ingredients_with_gemini(extracted_text: str, user_sensitivities: str):
    """
    Gemini API'ye doğrudan metin analizi isteği gönderir.
    """
    if not extracted_text.strip():
        raise ValueError("Analiz edilecek içerik metni boş olamaz.")

    user_prompt = f"""Ürün ambalajının arkasında yazan metin: {extracted_text}
    Kullanıcının özel hassasiyetleri: {user_sensitivities} 
    Yukarıdaki metni analiz et ve içeriklerin toksisite durumunu değerlendir.
    """

    try:
        response = GEMINI_MODEL.generate_content(user_prompt)

        raw_text = response.text

        # JSON bloğunu bul
        if not raw_text.strip().startswith('{') or not raw_text.strip().endswith('}'):
            json_start = raw_text.find('{')
            json_end = raw_text.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                raw_text = raw_text[json_start : json_end + 1]
            else:
                raise ValueError(f"Gemini çıktısı geçerli bir JSON bloğu içermiyor:\n{raw_text}")

        structured_output = json.loads(raw_text)
        return structured_output

    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini çıktısı JSON formatında değil veya bozuk:\n{e}\nRaw Output:\n{raw_text}")
    except Exception as e:
        raise Exception(f"Gemini API çağrısı sırasında hata oluştu:\n{e}")


def extract_ingredients(image_file)-> str:
    """
    Mini OCR tool.

    Gets request.FILES.image object. Analyze the image with google vision API and extraxted the text on the image.
    
    """
    try: 
        content = image_file.read()
        image = vision.Image(content=content)

        # Perform label detection
        response = VISION_CLIENT.text_detection(image=image)
        texts = response.text_annotations
        
        if not texts:
            return ""

        detected_text = texts[0].description

        return detected_text

    except Exception as e:
            raise Exception(f"Google Vision API ile metin çıkarılırken hata oluştu: {e}")
    


# def analyse_ingredients_with_gemini(extracted_text: str):
#     prompt = f"Ürün mbalajının arkasında yazan metin:\n{extracted_text}"

#     payload = {
#         "contents": [
#             {"role": "system", "parts": [{"text": SYSTEM_PROMPT}]},
#             {"role": "user", "parts": [{"text": prompt}]}
#         ]
#     }

#     params = {
#         "key": GEMINI_API_KEY
#     }

#     headers = {
#         "Content-Type": "application/json"
#     }

#     response = requests.post(
#         GEMINI_API_URL, # Doğru URL'i kullanıyoruz
#         json=payload,
#         headers=headers,
#         params=params # Anahtarı params olarak gönderiyoruz
#     )


#     if response.status_code != 200:
#         raise Exception(f"Gemini API hatası: {response.text}")

#     gemini_output = response.json()
#     raw_text = gemini_output['candidates'][0]['content']['parts'][0]['text']

#     try:
#         structured_output = json.loads(raw_text)
#         return structured_output
#     except json.JSONDecodeError:
#         raise ValueError(f"Gemini çıktısı JSON formatında değil:\n{raw_text}")

