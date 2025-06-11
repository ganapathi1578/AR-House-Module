# streams/views.py

import os
from pathlib import Path
import json
import datetime
from django.conf import settings
from django.http import JsonResponse, Http404, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import hashers, authenticate
import secrets
from .models import APIKey,  Feedback
from django.views.decorators.csrf import csrf_exempt
from .decorators import require_api_key
from django.views.decorators.http import require_POST
import uuid
import subprocess
import requests




# === Helper to build absolute filesystem paths ===
def get_camera_folder(date_str, camera_id):
    """
    Returns the absolute folder path for a given date (YYYY-MM-DD) and camera_id,
    e.g. MEDIA_ROOT/2025-06-04/cam0
    """
    base = settings.MEDIA_ROOT
    folder = os.path.join(base, date_str, camera_id)
    if os.path.isdir(folder):
        return folder
    raise Http404(f"Folder not found for date='{date_str}', camera='{camera_id}'")


# === 1) List available dates (directories under MEDIA_ROOT) ===
@require_api_key
@require_GET
def list_dates(request):
    """
    GET /api/dates/
    Returns JSON: { "dates": ["2025-06-04", "2025-06-05", ...] }
    """
    media_root = settings.MEDIA_ROOT
    try:
        all_entries = os.listdir(media_root)
    except FileNotFoundError:
        all_entries = []

    dates = []
    for name in all_entries:
        full_path = os.path.join(media_root, name)
        try:
            if os.path.isdir(full_path):
                datetime.datetime.strptime(name, "%Y-%m-%d")
                dates.append(name)
        except (ValueError, TypeError):
            continue

    dates.sort(reverse=True)
    return JsonResponse({"dates": dates})

# === 2) List available cameras for a given date ===
@require_GET
@require_api_key
def list_cameras_for_date(request, date_str):
    """
    GET /api/dates/<date_str>/cameras/
    Returns JSON: { "cameras": ["cam0", "cam1", ...] }
    """
    date_folder = os.path.join(settings.MEDIA_ROOT, date_str)
    if not os.path.isdir(date_folder):
        raise Http404(f"Date '{date_str}' not found.")

    cameras = [name for name in os.listdir(date_folder)
               if os.path.isdir(os.path.join(date_folder, name))]
    cameras.sort()
    return JsonResponse({"cameras": cameras})

# === 3) Return metadata_index.json for <date>/<camera> ===
@require_GET
@require_api_key
def metadata_index(request, date_str, camera_id):
    """
    GET /api/streams/<date_str>/<camera_id>/metadata_index/
    Returns the contents of metadata_index.json as JSON.
    """
    folder = get_camera_folder(date_str, camera_id)
    index_path = os.path.join(folder, "metadata_index.json")
    if not os.path.isfile(index_path):
        raise Http404("metadata_index.json not found.")

    with open(index_path, 'r') as f:
        data = json.load(f)
    return JsonResponse(data, safe=False)

# === 4) Redirect to the HLS playlist (index.m3u8) ===
@require_GET
@require_api_key
def playlist_redirect(request, date_str, camera_id):
    """
    GET /api/streams/<date_str>/<camera_id>/playlist/
    Redirects (302) to the static URL for index.m3u8 under /media/.
    """
    # Validate folder exists
    _ = get_camera_folder(date_str, camera_id)
    
    scheme = request.scheme
    host = request.META.get('HTTP_HOST', 'localhost:8000')

    # Combine full media URL path
    media_url = settings.MEDIA_URL.rstrip('/')
    playlist_url = f"{scheme}://{host}{media_url}/{date_str}/{camera_id}/index.m3u8"
    return JsonResponse({'playlist_url': playlist_url})

# === 5) List the last N segments (for convenience) ===
@require_GET
@require_api_key
def list_recent_segments(request, date_str, camera_id):
    """
    GET /api/streams/<date_str>/<camera_id>/recent/?count=10
    Returns JSON: { "segments": [ "segment_00023.ts", ... ], "metadata": [ "segment_00023.json", ... ] }
    """
    folder = get_camera_folder(date_str, camera_id)
    try:
        all_files = os.listdir(folder)
    except FileNotFoundError:
        return JsonResponse({"segments": [], "metadata": []})

    ts_files = sorted(
        [f for f in all_files if f.startswith("segment_") and f.endswith(".ts")]
    )
    count = 10
    try:
        count = int(request.GET.get("count", "10"))
    except ValueError:
        pass

    ts_recent = ts_files[-count:]
    js_recent = [f.replace('.ts', '.json') for f in ts_recent]

    return JsonResponse({
        "segments": ts_recent,
        "metadata": js_recent
    })

# === 6) Return all camera + date info in one call ===
@require_GET
@require_api_key
def all_streams_manifest(request):
    """
    GET /api/streams/manifest/
    Returns:
      {
        "dates": {
          "2025-06-04": ["cam0", "cam1"],
          "2025-06-03": ["cam0"]
        }
      }
    """
    media_root = settings.MEDIA_ROOT
    manifest = {}
    try:
        for date_str in os.listdir(media_root):
            full_date = os.path.join(media_root, date_str)
            try:
                datetime.datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            if not os.path.isdir(full_date):
                continue

            cams = [
                cam for cam in os.listdir(full_date)
                if os.path.isdir(os.path.join(full_date, cam))
            ]
            if cams:
                manifest[date_str] = sorted(cams)
    except FileNotFoundError:
        pass

    return JsonResponse({"dates": manifest})


# Helper: Check if user is admin
def is_admin(user):
    return user.is_superuser


# Helper: Reusable authentication function
def get_authenticated_user(request):
    username = request.POST.get('username')
    password = request.POST.get('password')
    if not username or not password:
        return None, JsonResponse({'error': 'Missing credentials'}, status=400)

    user = authenticate(username=username, password=password)
    if user is None:
        return None, JsonResponse({'error': 'Invalid credentials'}, status=400)

    return user, None


# 1. Admin-only: Create user
@csrf_exempt
@user_passes_test(is_admin)
def create_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')

        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': 'Username already exists'}, status=400)

        user = User.objects.create(
            username=username,
            email=email,
            password=hashers.make_password(password)
        )
        return JsonResponse({'message': 'User created successfully', 'username': user.username})


# 2. Register or get API key
@csrf_exempt
def register_or_get_key(request):
    if request.method == 'POST':
        user, error = get_authenticated_user(request)
        if error:
            return error

        api_key_obj, created = APIKey.objects.get_or_create(user=user)
        if created or not api_key_obj.key:
            api_key_obj.key = secrets.token_hex(20)
            api_key_obj.save()

        return JsonResponse({
            'username': user.username,
            'api_key': api_key_obj.key,
            'created_at': api_key_obj.created_at.isoformat()
            })
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@require_api_key
def view_api_key(request):
    """
    POST /view-api-key/
    Requires API key in headers. Returns current user's API key.
    """
    user = request.user
    try:
        api_key_obj = APIKey.objects.get(user=user)
        return JsonResponse({
            'username': user.username,
            'api_key': api_key_obj.key,
            'created_at': api_key_obj.created_at.isoformat()
        })
    except APIKey.DoesNotExist:
        return JsonResponse({'error': 'API key not found'}, status=404)

# 4. Regenerate API key
@csrf_exempt
def regenerate_api_key(request):
    if request.method == 'POST':
        user, error = get_authenticated_user(request)
        if error:
            return error

        try:
            api_key_obj = APIKey.objects.get(user=user)
            api_key_obj.key = secrets.token_hex(20)
            api_key_obj.save()
            return JsonResponse({
                'message': 'API key regenerated',
                'username': user.username,
                'api_key': api_key_obj.key,
                'created_at': api_key_obj.created_at.isoformat()})
        except APIKey.DoesNotExist:
            return JsonResponse({'error': 'API key not found'}, status=404)


@require_api_key
@csrf_exempt
def handle_feedback(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        data = request.POST
        start_time = data['start_time']
        end_time = data['end_time']
        user_id = data['user_id']
        feedback_text = data['feedback_text']
        video_url = data['video_url']

        # Validate time format (HH:MM:SS)
        def validate_time_format(t):
            try:
                h, m, s = map(int, t.split(':'))
                if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
                    raise ValueError
                return True
            except ValueError:
                return False

        if not (validate_time_format(start_time) and validate_time_format(end_time)):
            return JsonResponse({'error': 'Invalid time format'}, status=400)

        # Generate full UUID for uniqueness
        unique_id = str(uuid.uuid4())

        # Define output path in root/feedbackvideos
        output_filename = f"{unique_id}.mp4"
        FEEDBACK_VIDEO_DIR = Path(settings.BASE_DIR) / 'feedbackvideos'
        output_path = FEEDBACK_VIDEO_DIR / output_filename

        # Ensure folder exists
        FEEDBACK_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

        # Calculate duration from start and end times
        def time_to_seconds(t):  # "HH:MM:SS" → seconds
            h, m, s = map(int, t.split(':'))
            return h * 3600 + m * 60 + s

        duration = time_to_seconds(end_time) - time_to_seconds(start_time)
        if duration <= 0:
            return JsonResponse({'error': 'End time must be after start time'}, status=400)

        # FFmpeg command to trim video
        cmd = [
            'ffmpeg',
            '-ss', start_time,
            '-i', video_url,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-strict', '-2',
            str(output_path),
            '-y'
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            return JsonResponse({'error': 'Video processing failed'}, status=500)

        # Save to SQLite model
        feedback = Feedback.objects.create(
            unique_id=unique_id,
            user_id=user_id,
            feedback_text=feedback_text,
            video_url=video_url,
            trimmed_video=f"feedbackvideos/{output_filename}",
            start_time=start_time,
            end_time=end_time
        )

        # Send to central server
        """try:
            with open(output_path, 'rb') as f:
                response = requests.post(
                    'http://central.server.domain/api/upload/',
                    data={
                        'user_id': user_id,
                        'feedback_text': feedback_text,
                        'start_time': start_time,
                        'end_time': end_time,
                        'unique_id': unique_id,
                    },
                    files={'video': (output_filename, f, 'video/mp4')}
                )
                if response.status_code != 200:
                    return JsonResponse({'error': f'Failed to upload to central server: {response.text}'}, status=500)
        except Exception as e:
            return JsonResponse({'error': f'Error sending to central server: {str(e)}'}, status=500)

        return JsonResponse({'status': 'success', 'id': unique_id})"""

    except KeyError:
        return JsonResponse({'error': 'Missing required fields'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)