from django.http import JsonResponse
from camera_integration.models import Camera
from django.contrib.auth.decorators import login_required

@login_required
def get_hls_url(request, cam_id):
    try:
        camera = Camera.objects.get(id=cam_id, user=request.user)
        stream_url = f"http://your-server-ip:8000/live_{cam_id}.m3u8"
        return JsonResponse({'stream_url': stream_url})
    except Camera.DoesNotExist:
        return JsonResponse({'error': 'Camera not found or access denied'}, status=403)
