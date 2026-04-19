"""
Template helpers so the same templates work for salons (barbershops)
and the new venue categories (tennis courts, computer cafes, billiard
halls, restaurants).

Usage in templates:

    {% load venue_labels %}

    <h5>{{ salon|resource_label_plural }}</h5>      -> "Masters" / "Courts" / "PCs" / "Tables"

    {% for m in salon.masters.all %}
        {{ m.name }} — {{ salon|resource_label_single }}
    {% endfor %}

    {{ service|price_per_hour_display }}             -> "80 000 / час"
    {% if salon|is_time_based %} per-hour UI {% endif %}
"""

from decimal import Decimal

from django import template
from django.utils.translation import gettext_lazy as _, pgettext_lazy

register = template.Library()


# ---------------------------------------------------------------------------
# MAP: category slug (or parent slug) -> resource labels
# ---------------------------------------------------------------------------
# Keys are the *parent* category slugs. We match by walking up the MPTT tree.
# Fallback is "master"-style labels.
# ---------------------------------------------------------------------------

_RESOURCE_LABELS = {
    "paddle-tennis":  {"single": _("Court"),    "plural": _("Courts"),    "icon": "bi-trophy"},
    "big-tennis":     {"single": _("Court"),    "plural": _("Courts"),    "icon": "bi-circle"},
    "computer-cafe":  {"single": _("Station"),  "plural": _("Stations"),  "icon": "bi-pc-display"},
    "billiard":       {"single": _("Table"),    "plural": _("Tables"),    "icon": "bi-circle-fill"},
    "restaurant":     {"single": _("Table"),    "plural": _("Tables"),    "icon": "bi-cup-hot"},
}

# Categories that are time-based (priced per hour)
_TIME_BASED_SLUGS = {"paddle-tennis", "big-tennis", "computer-cafe", "billiard"}


def _root_slug_for(salon):
    """Walk up the MPTT tree to the root category slug."""
    cat = getattr(salon, "category", None)
    if not cat:
        return None
    try:
        root = cat.get_root()
    except Exception:
        root = cat
    return root.slug if root else None


@register.filter
def resource_label_single(salon):
    """
    Returns the singular label for a salon's 'master' concept.
    - Tennis salon   -> "Court"
    - Computer cafe  -> "Station"
    - Billiard       -> "Table"
    - Restaurant     -> "Table"
    - Anything else  -> "Master"
    """
    slug = _root_slug_for(salon)
    return _RESOURCE_LABELS.get(slug, {}).get("single", _("Master"))


@register.filter
def resource_label_plural(salon):
    slug = _root_slug_for(salon)
    return _RESOURCE_LABELS.get(slug, {}).get("plural", _("Masters"))


@register.filter
def resource_icon(salon):
    slug = _root_slug_for(salon)
    return _RESOURCE_LABELS.get(slug, {}).get("icon", "bi-person-badge")


@register.filter
def is_time_based(salon):
    """True for tennis / billiard / computer cafe (per-hour pricing)."""
    return _root_slug_for(salon) in _TIME_BASED_SLUGS


@register.filter
def is_restaurant(salon):
    return _root_slug_for(salon) == "restaurant"


# ---------------------------------------------------------------------------
# PRICING
# ---------------------------------------------------------------------------

@register.filter
def price_per_hour(service):
    """
    Returns the per-hour price as a Decimal (or None if duration is 0).
    For a service that costs 150000 for 120 minutes -> 75000.
    """
    if not service or not service.duration_minutes:
        return None
    try:
        hours = Decimal(service.duration_minutes) / Decimal(60)
        if hours == 0:
            return None
        return (Decimal(service.price) / hours).quantize(Decimal("1"))
    except Exception:
        return None


@register.filter
def price_per_hour_display(service):
    """
    Human-friendly per-hour price.
    Returns "" if not applicable (e.g. restaurant reservation with 0 price).
    """
    p = price_per_hour(service)
    if p is None or p == 0:
        return ""
    # Format like "80 000 so'm / час" — use gettext for the unit label.
    return f"{p:,.0f} / {_('hour')}".replace(",", " ")
