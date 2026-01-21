from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def i18n(context, obj, field_base, default="ru"):
    request = context.get("request")
    lang = getattr(request, "LANGUAGE_CODE", default)
    if hasattr(obj, "get_i18n"):
        return obj.get_i18n(field_base, lang, default_lang=default)
    return ""
