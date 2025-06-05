# your_app/management/commands/start_chunk_pipeline.py

import os
import cv2
import time
import json
import queue
import threading
import subprocess
import datetime
#from ultralytics import YOLO
import random
from django.core.management.base import BaseCommand

# === Configuration ===
SEGMENT_DURATION = 2         # seconds per HLS segment
FPS = 30                     # target frames per second
MEDIA_ROOT = os.path.join(os.getcwd(), "media")  # where we store all chunks + metadata
RETRY_INTERVAL = 3           # seconds to wait before retrying camera open

# HLS settings: single bitrate (you can adjust bitrate as needed)
HLS_BITRATE = "2000k"
HLS_HEIGHT = 720   # we'll scale to 720p
FRAME_SIZE = (1280, 720)  # placeholder; replaced by actual camera resolution

# === Helpers ===

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def get_output_dir(camera_id):
    """
    Returns: <MEDIA_ROOT>/<YYYY-MM-DD>/<camera_id>/
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    out_dir = os.path.join(MEDIA_ROOT, today, camera_id)
    ensure_dir(out_dir)
    return out_dir

# === Pipeline Stages ===

def capture_frames(cam_index, frame_q):
    """
    Continuously capture frames from cam_index; put each frame into frame_q.
    If camera fails, retry after RETRY_INTERVAL.
    """
    while True:
        cap = cv2.VideoCapture(cam_index)
        if not cap.isOpened():
            print(f"[WARN] Camera {cam_index} not available. Retrying in {RETRY_INTERVAL}s.")
            time.sleep(RETRY_INTERVAL)
            continue

        print(f"[INFO] Camera {cam_index} opened successfully.")
        while True:
            ret, frame = cap.read()
            if not ret:
                print(f"[WARN] Camera {cam_index} capture failed; reopening.")
                break

            frame_q.put(frame)
            time.sleep(1.0 / FPS)

        cap.release()
        time.sleep(RETRY_INTERVAL)




FAKE_LABELS = ["person", "car", "bottle", "cat", "dog", "chair", "tree", "phone", "laptop", "book"]

def model_inference(frame_q, annotated_q):
    """
    Simulates model inference by generating random detections (1-3 per frame).
    """
    while True:
        try:
            frame = frame_q.get(timeout=1)
        except queue.Empty:
            time.sleep(0.1)
            continue

        ts = time.time()
        height, width, _ = frame.shape

        num_detections = random.randint(1, 3)
        metadata = []

        for _ in range(num_detections):
            label = random.choice(FAKE_LABELS)
            conf = round(random.uniform(0.5, 0.99), 3)

            x1 = random.randint(0, width // 2)
            y1 = random.randint(0, height // 2)
            x2 = random.randint(x1 + 10, width)
            y2 = random.randint(y1 + 10, height)

            metadata.append({
                "ts": ts,
                "label": label,
                "confidence": conf,
                "xmin": x1,
                "ymin": y1,
                "xmax": x2,
                "ymax": y2
            })

        annotated_q.put((frame, metadata, ts))


def stream_with_ffmpeg(camera_id, annotated_q):
    """
    Read (frame, metadata, ts) from annotated_q; pipe frames into FFmpeg to generate HLS chunks
    (no deletions) and write one JSON metadata file per chunk.
    """
    out_dir = get_output_dir(camera_id)
    # HLS segment pattern and playlist
    segment_pattern = os.path.join(out_dir, "segment_%05d.ts")
    playlist_path = os.path.join(out_dir, "index.m3u8")

    # Build FFmpeg command for a single HLS bitrate, no sliding-window deletions
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "rawvideo",
        "-pixel_format", "bgr24",
        "-video_size", f"{FRAME_SIZE[0]}x{FRAME_SIZE[1]}",
        "-framerate", str(FPS),
        "-i", "pipe:0",
        "-filter:v", f"scale=-2:{HLS_HEIGHT}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", HLS_BITRATE,
        "-g", str(FPS * SEGMENT_DURATION),
        "-sc_threshold", "0",
        "-f", "hls",
        "-hls_time", str(SEGMENT_DURATION),
        "-hls_list_size", "0",                      # keep all segments indefinitely
        "-hls_flags", "append_list+independent_segments",
        "-hls_segment_filename", segment_pattern,
        playlist_path
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    segment_buffer = []
    segment_start_ts = time.time()
    segment_index = 0
    metadata_index = []

    while True:
        try:
            frame, metadata, ts = annotated_q.get(timeout=1)
        except queue.Empty:
            time.sleep(0.1)
            continue

        # Feed raw frame data into FFmpeg stdin
        try:
            proc.stdin.write(frame.tobytes())
        except BrokenPipeError:
            print(f"[ERROR] FFmpeg pipe broken for {camera_id}; exiting stream thread.")
            break

        segment_buffer.extend(metadata)
        now = time.time()
        if now - segment_start_ts >= SEGMENT_DURATION:
            # Write metadata JSON for this chunk
            json_path = os.path.join(out_dir, f"segment_{segment_index:05d}.json")
            with open(json_path, "w") as f_json:
                json.dump(segment_buffer, f_json)

            metadata_index.append({
                "segment": segment_index,
                "metadata_file": os.path.basename(json_path)
            })
            segment_buffer = []
            segment_index += 1
            segment_start_ts = now

            # Update master metadata index
            index_path = os.path.join(out_dir, "metadata_index.json")
            with open(index_path, "w") as f_index:
                json.dump(metadata_index, f_index)


def start_pipeline_for_camera(cam_index):
    """
    For camera 'cam<index>', start threads:
      - capture_frames → frame_q
      - model_inference → annotated_q
      - stream_with_ffmpeg → HLS + JSON chunks
    """
    camera_id = f"cam{cam_index}"
    frame_q = queue.Queue(maxsize=50)
    annotated_q = queue.Queue(maxsize=50)

    # Detect actual camera resolution once
    cap_test = cv2.VideoCapture(cam_index)
    if cap_test.isOpened():
        ret, frame0 = cap_test.read()
        cap_test.release()
        if ret:
            h, w, _ = frame0.shape
            global FRAME_SIZE
            FRAME_SIZE = (w, h)
            print(f"[INFO] Camera {cam_index} resolution set to {FRAME_SIZE}")

    t_capture = threading.Thread(target=capture_frames, args=(cam_index, frame_q), daemon=True)
    t_infer   = threading.Thread(target=model_inference, args=(frame_q, annotated_q), daemon=True)
    t_stream  = threading.Thread(target=stream_with_ffmpeg, args=(camera_id, annotated_q), daemon=True)

    for t in (t_capture, t_infer, t_stream):
        t.start()

    return [t_capture, t_infer, t_stream]


# === Django Management Command ===
class Command(BaseCommand):
    help = "Start HLS-only chunk pipeline with metadata (no redundancy)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--cameras',
            nargs='+',
            type=int,
            default=[0],
            help="Camera indices, e.g. --cameras 0 1 2"
        )

    def handle(self, *args, **options):
        camera_indices = options['cameras']
        all_threads = []

        for cam_idx in camera_indices:
            print(f"[INFO] Launching pipeline for camera index {cam_idx}")
            th = threading.Thread(target=start_pipeline_for_camera, args=(cam_idx,), daemon=True)
            th.start()
            all_threads.append(th)

        print("[INFO] All pipelines launched. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("[INFO] Shutting down camera pipelines...")

# === Standalone Execution ===
if __name__ == '__main__':
    camera_sources = [0,1]  # change indices or add RTSP URLs as needed
    all_threads = []
    for cam_idx in camera_sources:
        print(f"[INFO] Starting pipeline for camera index {cam_idx}")
        th = threading.Thread(target=start_pipeline_for_camera, args=(cam_idx,), daemon=True)
        th.start()
        all_threads.append(th)

    print("[INFO] Pipelines running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[INFO] Exiting.")
