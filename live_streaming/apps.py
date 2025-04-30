from django.apps import AppConfig
import logging


class LiveStreamingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'live_streaming'

    def ready(self):
        """
        This method is called when the Django app is ready.
        You can place startup logic here, such as initializing FFmpeg management or logging setup.
        """
        from . import ffmpeg_utils  # Example: FFmpeg handler or stream manager module
        logger = logging.getLogger(__name__)
        logger.info("Live streaming app is ready.")
        # Optionally: start scheduled checks or preload stream configs
        # ffmpeg_utils.initialize_streams()
