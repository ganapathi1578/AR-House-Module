from django.urls import path
from . import views

urlpatterns = [
    # 1) List available dates
    path('api/dates/', views.list_dates, name='list_dates'),

    # 2) List cameras for a given date
    path('api/dates/<str:date_str>/cameras/', views.list_cameras_for_date, name='list_cameras'),

    # 3) Metadata index for a camera/date
    path(
        'api/streams/<str:date_str>/<str:camera_id>/metadata_index/',
        views.metadata_index,
        name='metadata_index'
    ),

    # 4) Redirect to HLS playlist (index.m3u8)
    path(
        'api/streams/<str:date_str>/<str:camera_id>/playlist/',
        views.playlist_redirect,
        name='playlist_redirect'
    ),

    # 5) List recent N segments + metadata
    path(
        'api/streams/<str:date_str>/<str:camera_id>/recent/',
        views.list_recent_segments,
        name='list_recent'
    ),

    # 6) Full manifest of all dates/cameras
    path('api/streams/manifest/', views.all_streams_manifest, name='all_streams_manifest'),
]
