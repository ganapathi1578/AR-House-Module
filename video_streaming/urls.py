from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admins/', admin.site.urls),
    path('', include('streams.urls')),  # include all our streaming endpoints
]

# In DEBUG, serve /media/ directly. In production, offload to nginx.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
