import os
import json
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client = AsyncGroq(api_key=api_key)


async def generate_dental_reply(
    user_text: str, history: str = "", dynamic_price_list: str = ""
) -> dict:
    current_prices = (
        dynamic_price_list
        if dynamic_price_list
        else "Прайс-лист уточняется. Консультация 2000 тг."
    )

    # Флаг для ИИ: есть ли уже история диалога
    is_first_message = history.strip() == ""
    greeting_instruction = (
        "Поздоровайся (вежливо и с эмодзи), так как это первое сообщение от пациента."
        if is_first_message
        else "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО ЗДОРОВАТЬСЯ! Диалог уже идет. Отвечай сразу по делу."
    )

    system_prompt = f"""
    Ты — ИИ-администратор премиум-стоматологии "Эстет". Твоя задача — продавать услуги, успокаивать пациентов и фиксировать точные записи.

    🚨 БАЗОВЫЕ ПРАВИЛА:
    1. ПРИВЕТСТВИЕ: {greeting_instruction}
    2. МЕДИЦИНА: Ты НЕ врач. Диагнозы по фото НЕ ставим (вежливо отказывай). НИКОГДА не пиши "лечение абсолютно без боли". Пиши: "Біздің клиникада заманауи анестезия қолданылады" / "Мы используем качественную анестезию".

    🌍 ЯЗЫКОВОЙ ПРОТОКОЛ (CRITICAL!):
    - Определи язык по ПЕРВЫМ СЛОВАМ пациента.
    - Если пациент начал на казахском (даже если потом вставил русские слова) — твой ответ (reply) должен быть НА 100% ТАЗА ҚАЗАҚ ТІЛІНДЕ. Ни одного русского слова в reply!
    - Если начал на русском — отвечай на 100% чистом русском.
    - Пиши полными, красивыми предложениями. Обращайся строго на "Сіз" / "Вы". Максимум 3-4 предложения.

    💎 МАРКЕТИНГ И ПРОДАЖИ (ОБЯЗАТЕЛЬНО К ИСПОЛНЕНИЮ):
    - ЭМПАТИЯ К БОЛИ: Жалуется на боль? СРАЗУ сочувствуй на выбранном языке ("Ой, тісіңіздің ауырғанына өкінемін..." / "Ой, сочувствую вашей боли...").
    - БРЕКЕТЫ (ТРИГГЕР): Если звучит слово "брекет", ты ОБЯЗАН написать эту фразу: "Консультация ортодонта бесплатная, а при установке брекетов мы дарим 3-этапную чистку и набор по уходу!" (ПЕРЕВЕДИ ЕЕ НА КАЗАХСКИЙ, если диалог идет на казахском).
    - ЦЕНЫ: Точную цену ставит врач после осмотра. 

    ⏳ ФИКСАЦИЯ ВРЕМЕНИ И CRM:
    - Если пациент назвал время (особенно ТОЧНОЕ, например "10:00") — СРАЗУ соглашайся, ставь action="booking_requested". ОБЯЗАТЕЛЬНО сохрани это точное время в поле appointment_time.

    💰 ПРЕЙСКУРАНТ:
    {current_prices}

    ИСТОРИЯ:
    {history if history else "[Начало диалога]"}

    СООБЩЕНИЕ ПАЦИЕНТА: "{user_text}"

    📝 ПРИМЕРЫ ИДЕАЛЬНЫХ ОТВЕТОВ (FEW-SHOT):
    Пример 1 (Шала-казахский + Боль + Точное время + Брекеты):
    Пациент: "Сәлеметсіз бе! Тісім қатты ауырып тұр... Коронка салғым келеді. И еще, консультация по брекетам платная ма? Ертең сағат 10:00-де бара аламын ба?"
    Ответ: {{"reply": "Сәлеметсіз бе! Тісіңіздің ауырғанына өкінемін, бірақ біздің заманауи анестезиямен емдеу жайлы өтеді. Коронканың бағасын дәрігер айтады, ал ортодонт кеңесі бізде тегін және брекет орнатсаңыз тазалау мен күтім жинағын сыйға тартамыз! Ертең сағат 10:00-ге жазылуыңызды администраторға табыстаймын. 🌸", "action": "booking_requested", "suggested_service": "Коронка, Брекеты", "appointment_time": "Завтра в 10:00"}}

    🚨 ФОРМАТ ОТВЕТА (СТРОГО JSON):
    {{
        "reply": "Текст (Полные предложения, 100% чистый язык пациента, не забывай про акции!)",
        "action": "none" ИЛИ "booking_requested",
        "suggested_service": "НА РУССКОМ: Суть (например: 'Кариес', 'Брекеты, Коронка')",
        "appointment_time": "НА РУССКОМ: Сохрани ТОЧНОЕ время (например: 'Завтра в 10:00', 'Сегодня вечером'). Если нет — null"
    }}
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    try:
        response = await client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        print(f"⚠️ Ошибка основной модели 70B: {e}")
        try:
            response = await client.chat.completions.create(
                messages=messages,
                model="llama-3.1-8b-instant",
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        except Exception as backup_e:
            print(f"❌ Ошибка резервной модели: {backup_e}")
            return {
                "reply": "Извините, у нас небольшая техническая заминка. Пожалуйста, подождите минутку или позвоните нам напрямую 🦷",
                "action": "none",
                "suggested_service": None,
                "appointment_time": None,
            }

    try:
        raw_content = response.choices[0].message.content.strip()
        parsed_data = json.loads(raw_content)

        if "action" not in parsed_data:
            parsed_data["action"] = "none"

        return parsed_data

    except json.JSONDecodeError as json_e:
        print(f"❌ Ошибка парсинга JSON от ИИ: {json_e}\nОтвет ИИ: {raw_content}")
        return {
            "reply": "Секундочку, уточняю информацию... 🦷",
            "action": "none",
            "suggested_service": None,
            "appointment_time": None,
        }