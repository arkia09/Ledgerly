from django.urls import path

from . import views

urlpatterns = [
    path("pages/", views.pages),
    path("pages/<int:pk>/", views.page_detail),
    path("pages/<int:pk>/confirm/", views.page_confirm),
    path("customers/", views.customer_list),
    path("customers/create/", views.customer_create),
    path("customers/<int:pk>/update/", views.customer_update),
    path("customers/<int:pk>/delete/", views.customer_delete),
    path("customers/<int:pk>/sales/", views.customer_sale),
    path("customers/<int:pk>/payments/", views.customer_payment),
    path("customers/<int:pk>/", views.customer_detail),
    path("reports/balances/", views.report_balances),
    path("reports/aging/", views.report_aging),
    path("rules/", views.rules),
]
