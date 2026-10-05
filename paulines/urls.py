from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect


# ✅ Smart root redirect:
# - If user is logged in → take them to admin dashboard
# - Otherwise → show admin login page
def root_redirect(request):
    if request.user.is_authenticated:
        return redirect("/admin/")
    return redirect("/admin/login/")


urlpatterns = [
    path("", root_redirect, name="root_redirect"),
    path("admin/", admin.site.urls),
    path("_nested_admin/", include("nested_admin.urls")),

    # ✅ CKEditor 5 file upload and browsing URLs
    path("ckeditor5/", include("django_ckeditor_5.urls")),
]

# ✅ Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
