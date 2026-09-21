"""Purpose: Expose a real Django admin only inside the test host."""
from django.contrib import admin
from django.urls import path
urlpatterns = [path("admin/", admin.site.urls)]
