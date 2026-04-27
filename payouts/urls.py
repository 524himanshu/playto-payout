from django.urls import path
from . import views

urlpatterns = [
    path('merchants/', views.MerchantListView.as_view()),
    path('merchants/<int:merchant_id>/', views.MerchantDetailView.as_view()),
    path('merchants/<int:merchant_id>/ledger/', views.MerchantLedgerView.as_view()),
    path('merchants/<int:merchant_id>/bank-accounts/', views.MerchantBankAccountsView.as_view()),
    path('merchants/<int:merchant_id>/payouts/', views.PayoutListView.as_view()),
    path('merchants/<int:merchant_id>/payouts/create/', views.PayoutCreateView.as_view()),
    path('merchants/<int:merchant_id>/payouts/<int:payout_id>/', views.PayoutDetailView.as_view()),
]