from django.urls import path

from . import views

urlpatterns = [
    path("pages/", views.pages),
    path("pages/<int:pk>/", views.page_detail),
    path("pages/<int:pk>/confirm/", views.page_confirm),
    path("customers/", views.customer_list),
    path("customers/<int:pk>/", views.customer_detail),
    path("reports/balances/", views.report_balances),
    path("reports/aging/", views.report_aging),
    path("reports/balances.png", views.report_balances_png),
    path("reports/aging.png", views.report_aging_png),
    path("rules/", views.rules),
]
