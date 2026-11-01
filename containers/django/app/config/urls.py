from django.contrib import admin
from django.http import HttpResponse
from django.urls import path


def home(request):
    return HttpResponse("Django works. Replace config/urls.py with your own site.")


urlpatterns = [path("", home), path("admin/", admin.site.urls)]
