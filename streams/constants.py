# streams/constants.py

import time

# -----------------
# API KEY / CAMERAS
# -----------------
VALID_API_KEYS = ['myapikey']    # Change 'myapikey' to something secure!
# We will dynamically discover cameras at runtime (0,1,2,…)
# But for “valid camera IDs” we’ll use strings "cam0", "cam1", … up to N-1.
# In practice, you might want a DB table. Here we'll build camera IDs in code.

# --------------
# STREAM SETUP
# --------------
# All HLS segments will go under:
#   <MEDIA_ROOT>/camera_data/<camera_id>/hls/...
#
# Each camera_id maps to a start UNIX timestamp (when streaming began).
# For simplicity, we’ll set start_ts = now() as soon as the capture thread starts.

SEGMENT_DURATION = 3  # seconds

# Store camera start times for windowing
CAMERA_START_TS = {}

# Example bitrate settings for multiple resolutions (height, bitrate, folder name)
BITRATE_SETTINGS = [
    (360, "500k", "low"),
    (720, "1200k", "medium"),
    (1080, "2500k", "high"),
]

