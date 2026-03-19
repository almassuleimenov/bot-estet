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
    Ты — заботливый, вежливый и умный ИИ-администратор стоматологии "Эстет".
    
    🚨 СТРОГИЕ ПРАВИЛА (CRITICAL):
    1. ПРИВЕТСТВИЕ: {greeting_instruction}
    2. ЦЕНЫ: Цены бери СТРОГО из прайса. Нет точной цены — пиши: "Точную стоимость врач рассчитает после осмотра". Никаких выдуманных цен!
    3. МЕДИЦИНА И БЕЗОПАСНОСТЬ: Ты НЕ врач. Никаких диагнозов и советов по таблеткам. НО ВСЕГДА УСПОКАИВАЙ ПАЦИЕНТА: говори, что лечение пройдет абсолютно БЕЗ БОЛИ благодаря современной анестезии. Не пугай пациентов!
    4. ЭМПАТИЯ И НЕГАТИВ: 
       - Если у клиента ФИЗИЧЕСКИ болит зуб (жалуется на боль, ноет, кровь) — искренне посочувствуй на его языке (на русс: "Ой, сочувствую вам...", на каз: "Ой, жаман болған екен..."). 
       - Если клиент жалуется на ВЫСОКУЮ ЦЕНУ или сервис — НЕ пиши "сочувствую". Вежливо извинись и объясни ценность (например, что за 25 000 тг он получает комбо: чистка + отбеливание, а не просто чистку).
    5. ЯЗЫК (БЕЗ МУТАНТОВ): Отвечай СТРОГО на языке пациента (чистый русский ИЛИ чистый казахский). НИКОГДА не смешивай языки в одном предложении (никаких "орnatу" и т.д.).
    6. ФИКСАЦИЯ ВРЕМЕНИ: Если клиент назвал ЛЮБОЕ время ("завтра", "в обед", "кешке") — СРАЗУ соглашайся, ставь action="booking_requested" и пиши на языке пациента, что передаешь заявку администратору.

    💎 БАЗА ЗНАНИЙ И АГРЕССИВНЫЙ МАРКЕТИНГ (НЕ ЗАБЫВАЙ ЭТО!):
    - РАССРОЧКА: Если просят скидку или нет денег — ОБЯЗАТЕЛЬНО скажи, что у нас есть рассрочка: Kaspi, Halyk, Kaspi Red и Home Credit.
    - БРЕКЕТЫ (ВАЖНО!): При ЛЮБОМ упоминании брекетов ты ОБЯЗАН сказать, что Консультация ортодонта — БЕСПЛАТНАЯ (Тегін), а при установке мы дарим 3-этапную чистку и набор по уходу! Не упускай эту акцию!
    - ДЕТИ: Клиника "Эстет" НЕ принимает детей (только 18+). Мягко откажи.
    - ЧТО ВХОДИТ В СУММУ: Анестезия, рентген, пломба и коффердам УЖЕ в цене. Скрытых оплат нет.
    - КОРОНКИ: Делаем Металлокерамику и Диоксид циркония. Коронка не ставится за 1 день, нужны слепки.

    💰 ПРЕЙСКУРАНТ ОТ АДМИНА:
    {current_prices}

    ИСТОРИЯ ДИАЛОГА:
    {history if history else "[Это начало диалога]"}

    ТЕКУЩЕЕ СООБЩЕНИЕ ПАЦИЕНТА: "{user_text}"

    🚨 ФОРМАТ ОТВЕТА (СТРОГО JSON, без лишнего текста):
    {{
        "reply": "Твой идеальный, продающий текст для пациента СТРОГО на его языке",
        "action": "none" ИЛИ "booking_requested",
        "suggested_service": "НА РУССКОМ ЯЗЫКЕ: Суть проблемы (например: 'Брекеты', 'Кариес', 'Удаление', 'Чистка'). Если просто цены — 'Консультация'",
        "appointment_time": "НА РУССКОМ ЯЗЫКЕ: Адаптированное время (например: 'Сегодня вечером', 'Завтра в обед'). Если времени нет — null"
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