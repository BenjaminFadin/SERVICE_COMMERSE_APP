from django.apps import AppConfig


class PcClubsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pc_clubs'

    def ready(self):
        import pc_clubs.signals  # noqa: F401
