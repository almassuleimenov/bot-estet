import os
import json
import re
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client = AsyncGroq(api_key=api_key)

def sanitize_json_output(raw_content: str) -> dict:
    """Очищает ответ Llama от Markdown (например, ```json ... ```) и парсит его."""
    clean_content = raw_content.strip()
    match = re.search(r'\{.*\}', clean_content, re.DOTALL)
    if match:
        clean_content = match.group(0)
    
    try:
        return json.loads(clean_content)
    except json.JSONDecodeError as e:
        print(f"Критическая ошибка парсинга после очистки: {e}. Сырой текст: {clean_content}")
        raise ValueError("Failed to parse JSON")

async def generate_dental_reply(
    user_text: str, 
    # ВАЖНО: history теперь должен быть СПИСКОМ СЛОВАРЕЙ, а не строкой!
    # Пример: [{"role": "user", "content": "Привет"}, {"role": "assistant", "content": "Здравствуйте!"}]
    history: list = None, 
    dynamic_price_list: str = ""
) -> dict:
    
    if history is None:
        history = []

    current_prices = (
        dynamic_price_list
        if dynamic_price_list
        else "Прайс-лист уточняется. Базовая консультация 2000 тг."
    )

    # 1. Промпт переведен на английский для лучшей логики Llama.
    # 2. Добавлен Chain-of-Thought (поле _reasoning).
    # 3. Использованы XML-теги для структуры.
    system_prompt = f"""
    You are an expert AI administrative assistant for "Эстет", a premium dental clinic.
    Your goal is to consult patients, enforce clinic policies, and identify booking intentions.
    
    <core_rules>
    1. LANGUAGE STRICTNESS: Identify if the user speaks Kazakh or Russian. Your "reply" MUST be 100% in that language. No mixing.
    2. BREVITY: Maximum 3-4 short sentences. 
    3. NO HALLUCINATIONS: NEVER invent doctors' names (e.g., do not say "Doctor Gauhar" or "Doctor Nurdaulet" unless they exist in the knowledge base). NEVER invent prices or services not listed below.
    4. EMPATHY: If the user complains about PHYSICAL PAIN (e.g., "болит", "ауырып"), start with brief sympathy. If NO pain is mentioned, maintain a polite, neutral tone.
    5. GREETING: If this is the FIRST message in the conversation, greet them politely. If it's an ongoing chat, DO NOT greet again, answer directly.
    </core_rules>
    
    <clinic_knowledge_base>
    [Orthodontics / Braces]
    - Orthodontist consultation is FREE (ТЕГІН). We select braces based on the bite.
    - PROMO: Installing braces includes a FREE 3-stage professional cleaning and a care kit.
    - Third-party braces: We usually don't correct braces installed elsewhere, but we invite them for an inspection.

    [Procedures]
    - Tooth Extraction (Жұлдыру): Ask how they feel if they mention recent extraction. 
    - Crowns: Metal-ceramic and Zirconium dioxide available. Details at consultation.
    - Cleaning: 3-stage (Ultrasound, Air Flow, Polishing) in one visit.
    - Whitening (Отбеливание): 10,000 KZT per session. REQUIRES cleaning beforehand.
    - 🔥 COMBO PROMO: Cleaning + Whitening = 25,000 KZT. (Always offer if one is mentioned).

    [Policies & Pricing]
    - Prices include everything (anesthesia, x-ray, fillings). Exact price is told by the doctor after inspection.
    - Current base prices: {current_prices}.
    - Financing: Halyk, Kaspi, Home Credit, Kaspi Red available.
    - 🛑 AGE RESTRICTION: 18+ ONLY. We DO NOT treat children. Politely refuse if asked.
    - Diagnostics: We DO NOT diagnose via photos. Invite for consultation.
    </clinic_clinic_knowledge_base>

    <output_format>
    You MUST respond in valid JSON format ONLY. 
    {{
        "_reasoning": "Step 1: Language check. Step 2: Pain check for empathy. Step 3: Match with knowledge base. Step 4: Check if user wants to book.",
        "reply": "Your final response to the user in their language.",
        "action": "Select 'booking_requested' if user suggests a specific time/day, otherwise 'none'.",
        "suggested_service": "Main service discussed (e.g., 'Брекеты', 'Удаление') in Russian, or null.",
        "appointment_time": "Time mentioned by user (e.g., 'Сегодня вечером') in Russian, or null."
    }}
    </output_format>
    """

    # Формируем правильную структуру сообщений для API
    messages = [{"role": "system", "content": system_prompt}]
    
    # Добавляем историю как отдельные роли, а не слепленный текст
    messages.extend(history)
    
    # Добавляем текущий запрос пользователя
    messages.append({"role": "user", "content": user_text})

    try:
        response = await client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.0, # КРИТИЧНО: Убрали стохастичность
            response_format={"type": "json_object"},
        )
        raw_content = response.choices[0].message.content
        parsed_data = sanitize_json_output(raw_content)

        # Подстраховка: если Llama забыла action
        if "action" not in parsed_data:
            parsed_data["action"] = "none"

        return parsed_data

    except Exception as e:
        print(f"⚠️ Ошибка основной модели 70B: {e}")
        # Фолбэк на 8B
        try:
            response = await client.chat.completions.create(
                messages=messages,
                model="llama-3.1-8b-instant",
                temperature=0.0, # Здесь тоже 0.0
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content
            parsed_data = sanitize_json_output(raw_content)
            
            if "action" not in parsed_data:
                parsed_data["action"] = "none"
                
            return parsed_data
            
        except Exception as backup_e:
            print(f"❌ Ошибка резервной модели: {backup_e}")
            return {
                "reply": "Извините, небольшая техническая заминка. Подождите минутку или позвоните нам напрямую 🦷",
                "action": "none",
                "suggested_service": None,
                "appointment_time": None,
            }