from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def health(request):
    return JsonResponse({"status": "ok", "service": "Playto Payout Engine"})

urlpatterns = [
    path('', health),
    path('admin/', admin.site.urls),
    path('api/v1/', include('payouts.urls')),
]