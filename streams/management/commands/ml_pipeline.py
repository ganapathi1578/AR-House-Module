import os
import cv2
import time
import json
import queue
import threading
import subprocess
import datetime
from ultralytics import YOLO
import torch
from django.core.management.base import BaseCommand

# Configuration
SEGMENT_DURATION = 2         # seconds per HLS segment
FPS = 10                    # target frames per second
MEDIA_ROOT = os.path.join(os.getcwd(), "media")  # where we store all chunks + metadata
RETRY_INTERVAL = 0.2          # seconds to wait before retrying camera open
HLS_BITRATE = "1000k"
HLS_HEIGHT = 720   # we'll scale to 720p
FRAME_SIZE = (1280, 720)  # placeholder; replaced by actual camera resolution

# Helpers
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def get_output_dir(camera_id):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    out_dir = os.path.join(MEDIA_ROOT, today, camera_id)
    ensure_dir(out_dir)
    return out_dir

# Pipeline Stages
def capture_frames(cam_index, frame_q):
    """
    Continuously capture frames from cam_index; put each (frame, capture_ts) into frame_q.
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
            capture_ts = time.time()  # Record timestamp immediately after frame capture
            if not ret:
                print(f"[WARN] Camera {cam_index} capture failed; reopening.")
                break
            frame_q.put((frame, capture_ts))
            time.sleep(1.0 / FPS)

        cap.release()
        time.sleep(RETRY_INTERVAL)

# Load YOLOv8 Nano model and optimize it
model = YOLO('yolov8n.pt')  # Nano variant
model.to('cuda:0')          # Use RTX 4060 GPU
# Optional: Quantize model to INT8 for speed (requires additional setup; commented out)
model = torch.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)

def model_inference(frame_q, annotated_q):
    """
    Performs real-time object detection with an optimized YOLOv8 Nano.
    """
    frame_skip = 2  # Process every 2nd frame to reduce load
    frame_count = 0

    while True:
        try:
            frame, capture_ts = frame_q.get(timeout=1)
        except queue.Empty:
            time.sleep(0.1)
            continue

        frame_count += 1
        if frame_count % frame_skip != 0:  # Skip frames
            annotated_q.put((frame, {"ts": capture_ts, "detections": []}))
            continue

        # Resize frame to lower resolution for faster inference
        small_frame = cv2.resize(frame, (320, 320))

        # Perform inference on GPU
        results = model(small_frame, device='cuda:0', imgsz=320)

        detections = []
        scale_x, scale_y = FRAME_SIZE[0] / 320, FRAME_SIZE[1] / 320
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                # Scale coordinates back to original frame size
                x1_new, x2_new = int(x1 * scale_x), int(x2 * scale_x)
                y1_new, y2_new = int(y1 * scale_y), int(y2 * scale_y)
                label = model.names[int(box.cls)]
                conf = float(box.conf)
                detections.append({
                    "label": label,
                    "confidence": conf,
                    "xmin": x1_new,
                    "ymin": y1_new,
                    "xmax": x2_new,
                    "ymax": y2_new
                })

        frame_metadata = {
            "ts": capture_ts,
            "detections": detections
        }
        annotated_q.put((frame, frame_metadata))

def stream_with_ffmpeg(camera_id, annotated_q):
    """
    Read (frame, frame_metadata) from annotated_q; pipe frames into FFmpeg to generate HLS chunks
    and write one JSON metadata file per chunk, aligned by capture timestamps.
    """
    out_dir = get_output_dir(camera_id)
    segment_pattern = os.path.join(out_dir, "segment_%05d.ts")
    playlist_path = os.path.join(out_dir, "index.m3u8")

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
        "-hls_list_size", "0",
        "-hls_flags", "append_list+independent_segments",
        "-hls_segment_filename", segment_pattern,
        playlist_path
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    segment_buffer = []  # List of frame metadata
    segment_start_ts = None
    segment_index = 0
    metadata_index = []

    while True:
        try:
            frame, frame_metadata = annotated_q.get(timeout=1)
        except queue.Empty:
            time.sleep(0.1)
            continue

        capture_ts = frame_metadata["ts"]
        if segment_start_ts is None:
            segment_start_ts = capture_ts

        # Feed raw frame data into FFmpeg stdin
        try:
            proc.stdin.write(frame.tobytes())
        except BrokenPipeError:
            print(f"[ERROR] FFmpeg pipe broken for {camera_id}; exiting stream thread.")
            break

        # Accumulate frame metadata
        segment_buffer.append(frame_metadata)

        # Check if we need to start a new segment based on capture time
        if capture_ts - segment_start_ts >= SEGMENT_DURATION:
            json_path = os.path.join(out_dir, f"segment_{segment_index:05d}.json")
            with open(json_path, "w") as f_json:
                json.dump(segment_buffer, f_json)
            metadata_index.append({
                "segment": segment_index,
                "metadata_file": os.path.basename(json_path)
            })
            segment_buffer = []
            segment_index += 1
            segment_start_ts = None  # Next frame sets the new start time

            # Update master metadata index every 10 segments
            if segment_index % 10 == 0:
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
    t_infer = threading.Thread(target=model_inference, args=(frame_q, annotated_q), daemon=True)
    t_stream = threading.Thread(target=stream_with_ffmpeg, args=(camera_id, annotated_q), daemon=True)

    for t in (t_capture, t_infer, t_stream):
        t.start()

    return [t_capture, t_infer, t_stream]

# Django Management Command
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
            threads = start_pipeline_for_camera(cam_idx)
            all_threads.extend(threads)

        print("[INFO] All pipelines launched. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("[INFO] Shutting down camera pipelines...")

# Standalone Execution
if __name__ == '__main__':
    camera_sources = [0, 1]  # Change indices or add RTSP URLs as needed
    all_threads = []

    for cam_idx in camera_sources:
        print(f"[INFO] Starting pipeline for camera index {cam_idx}")
        threads = start_pipeline_for_camera(cam_idx)
        all_threads.extend(threads)

    print("[INFO] Pipelines running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[INFO] Exiting.")