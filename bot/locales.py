TEXTS = {
    "uz": {
        "choose_language": "🌐 Tilni tanlang / Выберите язык:",
        "language_selected": "✅ Til tanlandi: O'zbekcha",
        "welcome": (
            "👋 Assalomu alaykum, {name}!\n\n"
            "Service Commerse botiga xush kelibsiz!\n\n"
            "Quyidagi tugmadan foydalaning:"
        ),
        "services_button": "🛍 Xizmatlar",
        "change_language_button": "🌐 Tilni o'zgartirish",
        "visit_website": "🌐 Saytga o'tish",
        "services_message": "Xizmatlarimiz bilan tanishish uchun saytimizga tashrif buyuring:",
    },
    "ru": {
        "choose_language": "🌐 Выберите язык / Tilni tanlang:",
        "language_selected": "✅ Язык выбран: Русский",
        "welcome": (
            "👋 Здравствуйте, {name}!\n\n"
            "Добро пожаловать в бот Service Commerse!\n\n"
            "Используйте кнопку ниже:"
        ),
        "services_button": "🛍 Сервисы",
        "change_language_button": "🌐 Изменить язык",
        "visit_website": "🌐 Перейти на сайт",
        "services_message": "Для ознакомления с нашими услугами посетите наш сайт:",
    },
}


def get_text(lang: str, key: str, **kwargs) -> str:
    text = TEXTS.get(lang, TEXTS["uz"]).get(key, "")
    if kwargs:
        text = text.format(**kwargs)
    return text