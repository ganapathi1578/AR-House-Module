# streams/views.py

import os
import json
import datetime
from django.conf import settings
from django.http import JsonResponse, Http404, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_GET

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
def playlist_redirect(request, date_str, camera_id):
    """
    GET /api/streams/<date_str>/<camera_id>/playlist/
    Redirects (302) to the static URL for index.m3u8 under /media/.
    """
    # Validate folder exists
    _ = get_camera_folder(date_str, camera_id)
    
    media_url = settings.MEDIA_URL.rstrip('/')
    playlist_url = f"{media_url}/{date_str}/{camera_id}/index.m3u8"
    return HttpResponseRedirect(playlist_url)

# === 5) List the last N segments (for convenience) ===
@require_GET
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
