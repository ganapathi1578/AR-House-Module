# AR-House-Module

AR-House-Module is a Django + OpenCV-based real-time camera action recognition system designed to process live camera streams, generate video segments, store metadata, and provide a web interface to interact with the processed streams. It also integrates Nginx for efficient static/media serving and deployment.

---

## ⚙️ Features

- 🎥 Multi-camera real-time stream processing.
- 🧠 Action recognition pipeline integrated via a Django custom command.
- 🌐 Web interface and APIs to preview, stream, and interact with video content.
- 📁 Metadata and video segmentation with HLS (HTTP Live Streaming) support.
- 🚀 Nginx-based reverse proxy deployment for performance and accessibility.

---

## 📁 Project Structure
AR-House-Module/
AR-House-Module/
├── Pipfile
├── Pipfile.lock
├── db.sqlite3
├── manage.py
├── nginx/
│   ├── conf/
│   │   ├── fastcgi.conf
│   │   ├── fastcgi_params
│   │   ├── koi-utf
│   │   ├── koi-win
│   │   ├── mime.types
│   │   ├── nginx.conf
│   │   ├── scgi_params
│   │   ├── uwsgi_params
│   │   └── win-utf
│   ├── contrib/
│   │   ├── README
│   │   ├── geo2nginx.pl
│   │   └── unicode2nginx/
│   │       ├── koi-utf
│   │       ├── unicode-to-nginx.pl
│   │       └── win-utf
│   │   └── vim/
│   │       ├── ftdetect/nginx.vim
│   │       ├── ftplugin/nginx.vim
│   │       ├── indent/nginx.vim
│   │       └── syntax/nginx.vim
│   ├── docs/
│   │   ├── CHANGES
│   │   ├── CHANGES.ru
│   │   ├── CODE_OF_CONDUCT.md
│   │   ├── CONTRIBUTING.md
│   │   ├── LICENSE
│   │   ├── OpenSSL.LICENSE
│   │   ├── PCRE.LICENCE
│   │   ├── README.md
│   │   ├── SECURITY.md
│   │   └── zlib.LICENSE
│   ├── html/
│   │   ├── 50x.html
│   │   └── index.html
│   ├── logs/
│   │   ├── access.log
│   │   ├── error.log
│   │   └── nginx.pid
│   ├── nginx.exe
│   └── temp/
│       ├── client_body_temp
│       ├── fastcgi_temp
│       ├── proxy_temp
│       ├── scgi_temp
│       └── uwsgi_temp
├── streams/
│   ├── __init__.py
│   ├── __pycache__/
│   │   ├── __init__.cpython-312.pyc
│   │   ├── admin.cpython-312.pyc
│   │   ├── apps.cpython-312.pyc
│   │   ├── constants.cpython-312.pyc
│   │   ├── models.cpython-312.pyc
│   │   ├── urls.cpython-312.pyc
│   │   └── views.cpython-312.pyc
│   ├── admin.py
│   ├── apps.py
│   ├── constants.py
│   ├── management/
│   │   └── commands/
│   │       ├── __pycache__/
│   │       │   ├── ml_pipeline.cpython-312.pyc
│   │       │   └── nginx_server.cpython-312.pyc
│   │       ├── ml_pipeline.py
│   │       └── nginx_server.py
│   ├── migrations/
│   │   ├── __init__.py
│   │   └── __pycache__/__init__.cpython-312.pyc
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── tests/
│   └── testing_boundingboxes.html
└── video_streaming/
    ├── __init__.py
    ├── __pycache__/
    │   ├── __init__.cpython-312.pyc
    │   ├── settings.cpython-312.pyc
    │   ├── urls.cpython-312.pyc
    │   └── wsgi.cpython-312.pyc
    ├── asgi.py
    ├── settings.py
    ├── urls.py
    └── wsgi.py


---

## 🧪 How to Run the Project

### 1️⃣ Start Nginx

Start Nginx server with the provided configuration:

```bash
cd nginx
./nginx.exe
```
#### 🔧 Ensure nginx.conf is configured with:
```nginx
listen your_ip/domain:port;
```
### 2️⃣ Start the Machine Learning Pipeline
Launch the ML camera processing service that receives frames and writes metadata and HLS segments:

```bash
python manage.py ml_pipeline --cameras 0 1
```
### 3️⃣ Start Django Server
Start Django on a local IP accessible from other devices on the same network:
```bash
python manage.py runserver  ip:port
```
## 🌐 Web Routes
| URL                     | Description                                          |
| ----------------------- | ---------------------------------------------------- |
| `/`                     | Homepage for entering camera IDs and previewing them |
| `/preview/<camera_id>/` | Preview JPEG snapshots of live feed                  |
| `/live/<camera_id>/`    | Fullscreen live player using video tag (HLS stream)  |
| `/admin/`               | Django admin dashboard                               |

## 📡 API Endpoints
These URLs allow access to video segments, metadata, and stream management:
| Endpoint                                          | Description                                          |
| ------------------------------------------------- | ---------------------------------------------------- |
| `/api/dates/`                                     | Lists all dates with recorded video data             |
| `/api/dates/<date>/cameras/`                      | Lists all cameras available for the specified date   |
| `/api/streams/<date>/<camera_id>/metadata_index/` | Fetches metadata index for a camera on a given date  |
| `/api/streams/<date>/<camera_id>/playlist/`       | Redirects to the HLS playlist `.m3u8` file           |
| `/api/streams/<date>/<camera_id>/recent/`         | Fetches recent segments and metadata for live replay |
| `/api/streams/manifest/`                          | Returns a complete manifest of all cameras and dates |

## 🔧 Notes
All media (frames, segments, metadata) is stored in `media/` under `camera_data/<camera_id>/<date>/`

Update camera source mappings in `streams/views.py` under the camdic dictionary.

Nginx must be restarted if you change config (`./nginx.exe -s reload`)

## 🛠️ Tech Stack
Python + Django

OpenCV

Nginx

HTML/CSS Templates

HLS (HTTP Live Streaming)

### 👤 Author
Created by Lakshmi Ganapathi Kodi as part of an IIT Internship project.
