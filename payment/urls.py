from django.urls import path

from .views import (
    PlanListView,
    SubscriptionView,
    TransactionDetailView,
    TransactionListView,
)

urlpatterns = [
    path("plans/", PlanListView.as_view(), name="plan-list"),
    path("transactions/", TransactionListView.as_view(), name="transaction-list"),
    path(
        "transactions/<int:pk>/",
        TransactionDetailView.as_view(),
        name="transaction-detail",
    ),
    path("paypal/subscribe/", SubscriptionView.as_view(), name="subscription"),
]
