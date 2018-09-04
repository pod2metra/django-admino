from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static

from django.contrib import admin as django_admin
import admino

admino.site.activated()

urlpatterns = [
    url(r'^admin/', admino.site.urls),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
