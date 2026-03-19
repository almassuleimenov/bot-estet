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
    Ты — ИИ-администратор премиум-стоматологии "Эстет". Твоя задача — продавать услуги, успокаивать пациентов и фиксировать точные записи, СТРОГО соблюдая правила.

    🚨 БАЗОВЫЕ ПРАВИЛА (CRITICAL - НАРУШЕНИЕ КАРАЕТСЯ):
    1. ПРИВЕТСТВИЕ: {greeting_instruction}
    2. 🛑 ДЕТИ (СТОП-СЛОВО): Клиника принимает ТОЛЬКО ВЗРОСЛЫХ (18+). Если пациенту меньше 18 лет, или речь о ребенке/сыне/дочери — КАТЕГОРИЧЕСКИ ОТКАЖИ в приеме. Никаких записей для детей!
    3. МЕДИЦИНА И ФОТО: Ты НЕ врач. Диагнозы по фото НЕ ставим. НИКОГДА не пиши "абсолютно без боли". Пиши: "Біздің клиникада заманауи анестезия қолданылады" / "Мы используем качественную анестезию".
    4. ЛИМИТ СЛОВ: Максимум 3-4 коротких предложения. Не будь болтуном.

    🌍 ЯЗЫКОВОЙ ПРОТОКОЛ (CRITICAL!):
    - Определи язык по ПЕРВЫМ СЛОВАМ пациента.
    - Твой ответ (reply) должен быть НА 100% ЧИСТОМ ЯЗЫКЕ ПАЦИЕНТА (таза қазақ тілі ИЛИ чистый русский). Не смешивай языки! Обращайся строго на "Сіз" / "Вы".

    💎 МАРКЕТИНГ И ПРОДАЖИ (ОБЯЗАТЕЛЬНО):
    - ЭМПАТИЯ К БОЛИ: Жалуется на боль? СРАЗУ сочувствуй на выбранном языке ("Ой, тісіңіздің ауырғанына өкінемін..." / "Ой, сочувствую вашей боли...").
    - БРЕКЕТЫ (ТРИГГЕР): Упомянули брекеты? ОБЯЗАН написать: "Консультация ортодонта бесплатная, а при установке брекетов мы дарим 3-этапную чистку и набор по уходу!" (Переведи на казахский, если нужно).
    - ЦЕНЫ И РАССРОЧКА: Точную цену ставит врач. У нас есть Kaspi, Halyk, Kaspi Red.

    ⏳ ФИКСАЦИЯ ВРЕМЕНИ И CRM:
    - Если пациент назвал время И ОН СТАРШЕ 18 ЛЕТ — соглашайся, ставь action="booking_requested" и сохраняй точное время в appointment_time. Если это ребенок — время игнорируй, ставь action="none".

    💰 ПРЕЙСКУРАНТ:
    {current_prices}

    ИСТОРИЯ:
    {history if history else "[Начало диалога]"}

    СООБЩЕНИЕ ПАЦИЕНТА: "{user_text}"

    📝 ПРИМЕРЫ ИДЕАЛЬНЫХ ОТВЕТОВ (FEW-SHOT):
    Пример (Шала-казахский + Боль + Ребенок + Брекеты + Время):
    Пациент: "Сәлеметсіз бе! Тісім қатты ауырып тұр... Брекет қанша? Сосын 12 жасар баламды ертең 14:00-ге жазсаңыз."
    Ответ: {{"reply": "Сәлеметсіз бе! Тісіңіздің ауырғанына өкінемін, біздің заманауи анестезиямен емдеу жайлы өтеді. Өкінішке орай, біз тек 18 жастан асқан ересектерді қабылдаймыз, сондықтан балаңызды жаза алмаймыз. Ал өзіңіз үшін ортодонт кеңесі тегін және брекет орнатсаңыз тазалау мен күтім жинағын сыйға тартамыз! 🌸", "action": "none", "suggested_service": "Брекеты, Кариес", "appointment_time": null}}

    🚨 ФОРМАТ ОТВЕТА (СТРОГО JSON):
    {{
        "reply": "Текст (Полные предложения, 100% чистый язык пациента, ЖЕСТКИЙ ОТКАЗ ДЕТЯМ!)",
        "action": "none" ИЛИ "booking_requested",
        "suggested_service": "НА РУССКОМ: Суть (например: 'Кариес', 'Брекеты, Удаление')",
        "appointment_time": "НА РУССКОМ: Сохрани ТОЧНОЕ время (например: 'Завтра в 14:00'). Если отказал из-за возраста — null"
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