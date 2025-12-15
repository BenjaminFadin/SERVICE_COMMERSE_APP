from django import template

register = template.Library()

@register.simple_tag
def i18n(obj, field_base, lang_code="ru"):
    """
    Usage:
      {% i18n obj "name" request.LANGUAGE_CODE as title %}
      {{ title }}

    Calls obj.get_i18n(field_base, lang_code) if available.
    """
    if obj is None:
        return ""

    lang_code = (lang_code or "ru").lower()

    # preferred: your mixin method
    if hasattr(obj, "get_i18n"):
        return obj.get_i18n(field_base, lang_code)

    # fallback: try name_ru/name_en/name_uz style fields
    field = f"{field_base}_{lang_code}"
    default_field = f"{field_base}_ru"
    val = getattr(obj, field, "") or getattr(obj, default_field, "")
    return val or ""
