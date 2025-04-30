import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from camera_integration.models import Camera


@database_sync_to_async
def get_camera_user(cam_id: int):
    return Camera.objects.get(id=cam_id).user


@database_sync_to_async
def get_camera_url(cam_id: int):
    return Camera.objects.get(id=cam_id).url


class CameraConsumer(AsyncWebsocketConsumer):
    """
    Sends the HLS stream URL over WebSocket after authentication and camera validation.
    """

    async def connect(self):
        self.user = self.scope["user"]
        self.cam_id = self.scope["url_route"]["kwargs"]["cam_id"]

        if self.user.is_anonymous:
            await self.close(code=4001, reason="Unauthorized")
            return

        if self.user != await get_camera_user(self.cam_id):
            await self.close(code=4001, reason="Unauthorized")
            return

        self.cam_url = await get_camera_url(self.cam_id)
        await self.accept()

        # Assume an ffmpeg process has already created the .m3u8 stream at a known path
        hls_stream_path = f"/media/streams/camera_{self.cam_id}/stream.m3u8"

        # Send the HLS stream path to frontend
        await self.send(text_data=json.dumps({
            "type": "hls_stream_url",
            "url": hls_stream_path
        }))

    async def disconnect(self, close_code):
        """
        Clean up if necessary when the socket disconnects.
        """
        pass
