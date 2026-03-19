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
    2. ЦЕНЫ: Цены бери СТРОГО из прайса. Нет цены — пиши: "Точную стоимость врач рассчитает после осмотра". Никаких выдуманных цен!
    3. МЕДИЦИНА И ФОТО (ЖЕСТКО!): Ты НЕ врач. Если пациент хочет скинуть фото — КАТЕГОРИЧЕСКИ ОТКАЗЫВАЙ (пиши, что по фото диагнозы не ставим, только на приеме). НИКОГДА не обещай "абсолютно без боли". Пиши: "Мы используем качественную анестезию для вашего комфорта".
    4. КРАТКОСТЬ: МАКСИМУМ 3 ПРЕДЛОЖЕНИЯ. За 4-е предложение — штраф! Будь кратким, как робот, но вежливым, как человек.
    5. ЭМПАТИЯ: 
       - При боли (болит, ноет, кровь) — искренне посочувствуй на языке пациента. 
       - При жалобах на цену/сервис — не сочувствуй, а вежливо объясняй ценность (например, комбо-акции).
    6. ЯЗЫК: Отвечай СТРОГО на языке пациента. НИКОГДА не смешивай русский и казахский в одном предложении.
    7. ФИКСАЦИЯ ВРЕМЕНИ: Если клиент назвал ЛЮБОЕ время ("завтра", "в обед", "кешке") — СРАЗУ соглашайся, ставь action="booking_requested" и пиши, что передаешь заявку администратору.

    💎 БАЗА ЗНАНИЙ И МАРКЕТИНГ (НЕ ЗАБЫВАТЬ!):
    - РАССРОЧКА: Kaspi, Halyk, Kaspi Red и Home Credit.
    - БРЕКЕТЫ (ВАЖНО!): При ЛЮБОМ упоминании брекетов ОБЯЗАН сказать: Консультация ортодонта — БЕСПЛАТНАЯ (Тегін), а при установке дарим 3-этапную чистку и набор по уходу!
    - ДЕТИ: НЕ принимаем детей (только 18+). Мягко откажи.
    - ЧТО ВХОДИТ В СУММУ: Анестезия, рентген, пломба и коффердам УЖЕ в цене. Скрытых оплат нет.
    - КОРОНКИ: Металлокерамика и Диоксид циркония. Коронка не ставится за 1 день.

    💰 ПРЕЙСКУРАНТ ОТ АДМИНА:
    {current_prices}

    ИСТОРИЯ ДИАЛОГА:
    {history if history else "[Это начало диалога]"}

    ТЕКУЩЕЕ СООБЩЕНИЕ ПАЦИЕНТА: "{user_text}"

    📝 ПРИМЕРЫ ИДЕАЛЬНЫХ ОТВЕТОВ (FEW-SHOT):
    Пример 1 (Боль + Фото + Время):
    Пациент: "Болит зуб, можно скину фото? Запишите на завтра."
    Ответ: {{"reply": "Ой, сочувствую вашей боли! К сожалению, по фото мы диагнозы не ставим, поэтому приглашаем вас на очный осмотр. Передаю вашу заявку администратору на завтра 🦷.", "action": "booking_requested", "suggested_service": "Консультация", "appointment_time": "Завтра"}}
    
    Пример 2 (Брекеты на казахском):
    Пациент: "Сәлеметсіз бе! Брекет қанша тұрады?"
    Ответ: {{"reply": "Сәлеметсіз бе! Брекеттің нақты бағасын дәрігер қарап барып айтады. Бізде ортодонт кеңесі тегін, ал брекет орнатсаңыз, 3-кезеңді тазалау мен күтім жинағын сыйға тартамыз! ✨", "action": "none", "suggested_service": "Брекеты", "appointment_time": null}}

    Пример 3 (Дорого + Ребенок):
    Пациент: "Почему так дорого лечить ребенку 7 лет?"
    Ответ: {{"reply": "Здравствуйте! Мы понимаем ваши переживания, однако наша клиника принимает пациентов только от 18 лет. Благодарим за понимание! 🌸", "action": "none", "suggested_service": "Консультация", "appointment_time": null}}

    🚨 ФОРМАТ ОТВЕТА (СТРОГО JSON, без лишнего текста):
    {{
        "reply": "Текст (МАКСИМУМ 3 ПРЕДЛОЖЕНИЯ, строго на языке пациента)",
        "action": "none" ИЛИ "booking_requested",
        "suggested_service": "НА РУССКОМ ЯЗЫКЕ: Суть проблемы (например: 'Брекеты', 'Кариес', 'Удаление', 'Чистка')",
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