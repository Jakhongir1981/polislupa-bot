"""Тексты бота на трёх языках: ru, uz (латиница), en."""

T = {
    "choose_lang": {
        "ru": "Выберите язык / Tilni tanlang / Choose language",
    },
    "welcome": {
        "ru": "Здравствуйте! Я помощник PolisLupa 🔍\nПодберу страховку для вас, семьи или бизнеса, проверю ваш договор или передам вопрос эксперту.\n\nЧто вас интересует?",
        "uz": "Assalomu alaykum! Men PolisLupa yordamchisiman 🔍\nSiz, oilangiz yoki biznesingiz uchun sug'urta tanlashga, shartnomangizni tekshirishga yoki savolingizni mutaxassisga yetkazishga yordam beraman.\n\nSizni nima qiziqtiradi?",
        "en": "Hello! I'm the PolisLupa assistant 🔍\nI can help you choose insurance for yourself, your family or your business, check your contract, or pass your question to an expert.\n\nWhat are you interested in?",
    },
    "btn_osago": {"ru": "🚗 ОСАГО — оформить онлайн", "uz": "🚗 OSAGO — onlayn rasmiylashtirish", "en": "🚗 OSAGO — buy online"},
    "btn_kasko": {"ru": "🛡 КАСКО — онлайн", "uz": "🛡 KASKO — onlayn", "en": "🛡 KASKO — online"},
    "btn_travel": {"ru": "✈️ Страховка в поездку — онлайн", "uz": "✈️ Sayohat sug'urtasi — onlayn", "en": "✈️ Travel insurance — online"},
    "btn_property": {"ru": "🏠 Имущество", "uz": "🏠 Mol-mulk", "en": "🏠 Property"},
    "btn_health": {"ru": "❤️ Здоровье и жизнь", "uz": "❤️ Sog'liq va hayot", "en": "❤️ Health & life"},
    "btn_business": {"ru": "🏢 Для бизнеса (юрлица)", "uz": "🏢 Biznes uchun (yuridik shaxslar)", "en": "🏢 For business"},
    "btn_other": {"ru": "📦 Другой вид страхования", "uz": "📦 Boshqa sug'urta turi", "en": "📦 Other insurance"},
    "property_obj": {
        "ru": "Что хотите застраховать? Например: квартира, дом, дача, офис, ремонт и техника",
        "uz": "Nimani sug'urta qilmoqchisiz? Masalan: kvartira, uy, dala hovli, ofis, ta'mir va texnika",
        "en": "What would you like to insure? E.g. apartment, house, country house, office, renovation and appliances",
    },
    "property_value": {
        "ru": "Город и примерная стоимость имущества?",
        "uz": "Shahar va mol-mulkning taxminiy qiymati?",
        "en": "City and approximate value of the property?",
    },
    "health_type": {
        "ru": "Что вас интересует? Например: медицинская страховка (ДМС), страхование жизни, от несчастного случая",
        "uz": "Sizni nima qiziqtiradi? Masalan: tibbiy sug'urta, hayot sug'urtasi, baxtsiz hodisalardan sug'urta",
        "en": "What are you interested in? E.g. health insurance, life insurance, accident insurance",
    },
    "health_who": {
        "ru": "Для кого и сколько человек? Укажите возраст. Например: я 35 лет, супруга 32, ребёнок 5",
        "uz": "Kim uchun va necha kishi? Yoshini ko'rsating. Masalan: men 35 yosh, turmush o'rtog'im 32, bola 5",
        "en": "For whom and how many people? Give ages. E.g. me 35, spouse 32, child 5",
    },
    "biz_company": {
        "ru": "Название компании и сфера деятельности?",
        "uz": "Kompaniya nomi va faoliyat sohasi?",
        "en": "Company name and line of business?",
    },
    "biz_need": {
        "ru": "Что нужно застраховать? Например: имущество и склад, грузы, транспорт компании, сотрудников (ДМС, НС), ответственность, строительно-монтажные работы, тендерные гарантии — или опишите своими словами",
        "uz": "Nimani sug'urta qilish kerak? Masalan: mol-mulk va ombor, yuklar, kompaniya transporti, xodimlar (tibbiy, baxtsiz hodisa), javobgarlik, qurilish-montaj ishlari, tender kafolatlari — yoki o'z so'zlaringiz bilan yozing",
        "en": "What needs insuring? E.g. property and warehouse, cargo, company vehicles, employees (health, accident), liability, construction works, tender guarantees — or describe in your own words",
    },
    "biz_contact": {
        "ru": "Как зовут контактное лицо и его должность?",
        "uz": "Mas'ul shaxsning ismi va lavozimi?",
        "en": "Contact person's name and position?",
    },
    "other_text": {
        "ru": "Опишите, что хотите застраховать, — эксперт подберёт вариант:",
        "uz": "Nimani sug'urta qilmoqchi ekanligingizni yozing — mutaxassis variant tanlab beradi:",
        "en": "Describe what you'd like to insure and an expert will find an option:",
    },
    "btn_review": {"ru": "🔍 Проверить мой полис", "uz": "🔍 Polisimni tekshirish", "en": "🔍 Check my policy"},
    "btn_question": {"ru": "💬 Вопрос эксперту", "uz": "💬 Mutaxassisga savol", "en": "💬 Ask an expert"},
    "btn_checklist": {"ru": "📋 Чек-лист: что делать при ДТП", "uz": "📋 Chek-list: YTHda nima qilish kerak", "en": "📋 Checklist: what to do after an accident"},
    "btn_channel": {"ru": "📢 Наш канал", "uz": "📢 Kanalimiz", "en": "📢 Our channel"},
    "btn_lang": {"ru": "🌐 Язык", "uz": "🌐 Til", "en": "🌐 Language"},
    "btn_cancel": {"ru": "↩️ В меню", "uz": "↩️ Menyuga", "en": "↩️ Menu"},
    "btn_done": {"ru": "✅ Готово", "uz": "✅ Tayyor", "en": "✅ Done"},
    "btn_no_policy": {"ru": "Полиса нет", "uz": "Polis yo'q", "en": "No policy yet"},
    "btn_share_phone": {"ru": "📱 Отправить номер", "uz": "📱 Raqamni yuborish", "en": "📱 Share phone number"},
    "btn_subscribe": {"ru": "📢 Подписаться", "uz": "📢 Obuna bo'lish", "en": "📢 Subscribe"},
    "btn_check_sub": {"ru": "✅ Я подписался", "uz": "✅ Obuna bo'ldim", "en": "✅ I've subscribed"},
    "btn_renew": {"ru": "🔁 Продлить полис", "uz": "🔁 Polisni uzaytirish", "en": "🔁 Renew policy"},

    # ОСАГО
    "osago_car": {
        "ru": "Марка, модель и год выпуска автомобиля?\nНапример: Chevrolet Cobalt 2021",
        "uz": "Avtomobil markasi, modeli va ishlab chiqarilgan yili?\nMasalan: Chevrolet Cobalt 2021",
        "en": "Car make, model and year?\nExample: Chevrolet Cobalt 2021",
    },
    "osago_end": {
        "ru": "Когда заканчивается текущий полис? Напишите дату в формате ДД.ММ.ГГГГ\nМы напомним заранее, чтобы вы не остались без страховки.",
        "uz": "Joriy polis qachon tugaydi? Sanani KK.OO.YYYY formatida yozing\nSug'urtasiz qolmasligingiz uchun oldindan eslatamiz.",
        "en": "When does your current policy expire? Write the date as DD.MM.YYYY\nWe'll remind you in advance so you're never uninsured.",
    },
    "bad_date": {
        "ru": "Не понял дату. Напишите, например: 15.03.2027 — или нажмите «Полиса нет».",
        "uz": "Sanani tushunmadim. Masalan: 15.03.2027 deb yozing — yoki «Polis yo'q» tugmasini bosing.",
        "en": "I couldn't read the date. Write e.g. 15.03.2027 — or tap “No policy yet”.",
    },
    # КАСКО
    "kasko_car": {
        "ru": "Марка, модель и год выпуска автомобиля?",
        "uz": "Avtomobil markasi, modeli va yili?",
        "en": "Car make, model and year?",
    },
    "kasko_value": {
        "ru": "Примерная стоимость автомобиля (в сумах или долларах)?",
        "uz": "Avtomobilning taxminiy narxi (so'm yoki dollarda)?",
        "en": "Approximate value of the car (in UZS or USD)?",
    },
    # Travel
    "travel_country": {"ru": "В какую страну едете?", "uz": "Qaysi davlatga borasiz?", "en": "Which country are you travelling to?"},
    "travel_dates": {
        "ru": "Даты поездки? Например: 10.01–20.01",
        "uz": "Sayohat sanalari? Masalan: 10.01–20.01",
        "en": "Travel dates? Example: 10.01–20.01",
    },
    "travel_people": {
        "ru": "Сколько человек едет и их возраст? Например: 2 взрослых, ребёнок 7 лет",
        "uz": "Necha kishi boradi va yoshlari? Masalan: 2 kattalar, 7 yoshli bola",
        "en": "How many travellers and their ages? Example: 2 adults, child aged 7",
    },
    # Разбор полиса
    "review_upload": {
        "ru": "Пришлите фото или PDF вашего договора страхования (можно несколько). Когда закончите — нажмите «Готово».\n\nЭксперт проверит: плюсы, минусы, скрытые риски и что стоит изменить.",
        "uz": "Sug'urta shartnomangizning rasmini yoki PDF faylini yuboring (bir nechta bo'lishi mumkin). Tugatgach «Tayyor» tugmasini bosing.\n\nMutaxassis tekshiradi: afzalliklar, kamchiliklar, yashirin xavflar va nimani o'zgartirish kerak.",
        "en": "Send a photo or PDF of your insurance contract (several are fine). When finished, tap “Done”.\n\nAn expert will check pros, cons, hidden risks and what to change.",
    },
    "review_got": {"ru": "Получено ✅ Ещё файлы — или «Готово».", "uz": "Qabul qilindi ✅ Yana fayl — yoki «Tayyor».", "en": "Received ✅ More files — or “Done”."},
    "review_empty": {"ru": "Сначала пришлите хотя бы один файл.", "uz": "Avval kamida bitta fayl yuboring.", "en": "Please send at least one file first."},
    # Вопрос
    "question_text": {"ru": "Напишите ваш вопрос:", "uz": "Savolingizni yozing:", "en": "Type your question:"},
    # Телефон
    "ask_phone": {
        "ru": "Оставьте номер телефона — эксперт свяжется с вами. Нажмите кнопку ниже или напишите номер.",
        "uz": "Telefon raqamingizni qoldiring — mutaxassis siz bilan bog'lanadi. Quyidagi tugmani bosing yoki raqamni yozing.",
        "en": "Leave your phone number and an expert will contact you. Tap the button below or type the number.",
    },
    "bad_phone": {"ru": "Похоже, номер неверный. Пример: +998 90 123 45 67", "uz": "Raqam noto'g'ri ko'rinadi. Misol: +998 90 123 45 67", "en": "That number looks wrong. Example: +998 90 123 45 67"},
    "thanks": {
        "ru": "Спасибо! Заявка принята ✅ Эксперт свяжется с вами в ближайшее время.\n\nПока ждёте — загляните в наш канал: там разборы и полезные советы.",
        "uz": "Rahmat! Ariza qabul qilindi ✅ Mutaxassis tez orada siz bilan bog'lanadi.\n\nKutayotganingizda kanalimizga kiring: u yerda foydali maslahatlar bor.",
        "en": "Thank you! Your request has been received ✅ An expert will contact you shortly.\n\nMeanwhile, check out our channel for useful tips.",
    },
    # Чек-лист
    "need_sub": {
        "ru": "Чек-лист доступен подписчикам нашего канала. Подпишитесь и нажмите «Я подписался».",
        "uz": "Chek-list kanalimiz obunachilari uchun. Obuna bo'ling va «Obuna bo'ldim» tugmasini bosing.",
        "en": "The checklist is available to our channel subscribers. Subscribe, then tap “I've subscribed”.",
    },
    "still_not_sub": {"ru": "Пока не вижу подписки 🙂 Попробуйте ещё раз через пару секунд.", "uz": "Hozircha obunani ko'rmayapman 🙂 Bir necha soniyadan keyin qayta urinib ko'ring.", "en": "I don't see the subscription yet 🙂 Try again in a few seconds."},
    "checklist": {
        "ru": (
            "📋 <b>Что делать при ДТП</b>\n\n"
            "1. Остановитесь, включите аварийку, выставьте знак аварийной остановки.\n"
            "2. Если есть пострадавшие — звоните 103 (скорая) и 102 (полиция).\n"
            "3. Не двигайте машины до фиксации, если нет угрозы безопасности.\n"
            "4. Сфотографируйте: общий план, повреждения, номера всех машин, следы и знаки.\n"
            "5. Возьмите данные второго участника: ФИО, телефон, номер полиса и страховую.\n"
            "6. Запишите контакты свидетелей.\n"
            "7. Ничего не подписывайте, если не согласны с формулировками.\n"
            "8. Сообщите в свою страховую как можно скорее — сроки уведомления указаны в полисе.\n\n"
            "Есть вопрос по вашей ситуации? Нажмите «Вопрос эксперту» 👇"
        ),
        "uz": (
            "📋 <b>YTHda nima qilish kerak</b>\n\n"
            "1. To'xtang, avariya chirog'ini yoqing, avariya to'xtash belgisini qo'ying.\n"
            "2. Jabrlanganlar bo'lsa — 103 (tez yordam) va 102 (politsiya)ga qo'ng'iroq qiling.\n"
            "3. Xavfsizlikka tahdid bo'lmasa, qayd etilgunga qadar mashinalarni siljitmang.\n"
            "4. Suratga oling: umumiy ko'rinish, shikastlar, barcha mashinalar raqamlari, izlar va belgilar.\n"
            "5. Ikkinchi ishtirokchining ma'lumotlarini oling: FISH, telefon, polis raqami va sug'urta kompaniyasi.\n"
            "6. Guvohlarning kontaktlarini yozib oling.\n"
            "7. Ta'riflarga rozi bo'lmasangiz, hech narsaga imzo chekmang.\n"
            "8. Sug'urta kompaniyangizga imkon qadar tezroq xabar bering — muddatlar polisda ko'rsatilgan.\n\n"
            "Vaziyatingiz bo'yicha savol bormi? «Mutaxassisga savol» tugmasini bosing 👇"
        ),
        "en": (
            "📋 <b>What to do after a car accident</b>\n\n"
            "1. Stop, turn on hazard lights, place the warning triangle.\n"
            "2. If anyone is injured, call 103 (ambulance) and 102 (police).\n"
            "3. Don't move the cars before the scene is recorded, unless it's unsafe.\n"
            "4. Take photos: wide shots, damage, all licence plates, marks and road signs.\n"
            "5. Get the other driver's details: name, phone, policy number and insurer.\n"
            "6. Note witnesses' contacts.\n"
            "7. Don't sign anything you disagree with.\n"
            "8. Notify your insurer as soon as possible — deadlines are in your policy.\n\n"
            "Questions about your case? Tap “Ask an expert” 👇"
        ),
    },
    # Напоминание о продлении
    "renew_reminder": {
        "ru": "Здравствуйте! Напоминаем: ваш полис ОСАГО заканчивается {date}. Оформим новый заранее, чтобы вы не остались без страховки?",
        "uz": "Assalomu alaykum! Eslatma: OSAGO polisingiz {date} da tugaydi. Sug'urtasiz qolmaslik uchun yangisini oldindan rasmiylashtiramizmi?",
        "en": "Hello! Reminder: your OSAGO policy expires on {date}. Shall we arrange a new one in advance so you stay covered?",
    },
    "renew_ok": {
        "ru": "Отлично! Передал эксперту — с вами свяжутся ✅",
        "uz": "Ajoyib! Mutaxassisga yetkazdim — siz bilan bog'lanishadi ✅",
        "en": "Great! I've passed this to an expert — they'll contact you ✅",
    },
}

PRODUCT_NAMES = {
    "osago": "ОСАГО",
    "kasko": "КАСКО",
    "travel": "Путешествие",
    "review": "Разбор полиса",
    "question": "Вопрос эксперту",
    "renew": "Продление ОСАГО",
    "property": "Имущество",
    "health": "Здоровье и жизнь",
    "business": "Юрлицо / бизнес",
    "other": "Другой вид страхования",
}

SOURCE_NAMES = {
    "ig": "Instagram",
    "tg": "Telegram-канал",
    "site": "Сайт PolisLupa",
    "ads": "Реклама Meta",
    "blog": "Статья блога",
}


def t(key: str, lang: str) -> str:
    variants = T[key]
    return variants.get(lang) or variants["ru"]
