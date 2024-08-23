from datetime import datetime
from drf_spectacular.utils import extend_schema, inline_serializer
from django.db import DatabaseError
from django.utils import timezone
from rest_framework import generics, status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from user_authentication.models import User
from .models import (
    Plan,
    Subscription,
    Transaction,
)
from .serializers import (
    PlanSerializer,
    SubscriptionInSerializer,
    SubscriptionOutSerializer,
    TransactionSerializer,
)
from django.utils import timezone


class PlanListView(generics.ListAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer


class SubscriptionView(generics.GenericAPIView):
    serializer_class = SubscriptionInSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="store_subscription",
        responses={
            status.HTTP_201_CREATED: SubscriptionOutSerializer,
            status.HTTP_400_BAD_REQUEST: inline_serializer(
                name="Error",
                fields={"error": serializers.CharField()},
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        user = validated_data["user"]
        plan = validated_data["plan"]
        number_of_cameras = validated_data["number_of_cameras"]
        paypal_subscription_id = validated_data["paypal_subscription_id"]
        start_date = timezone.now()
        end_date = start_date + timezone.timedelta(
            days=30 if plan.billing_cycle == "monthly" else 365
        )

        try:
            subscription = Subscription.objects.create(
                user=user,
                plan=plan,
                start_date=start_date,
                end_date=end_date,
                number_of_cameras=number_of_cameras,
                paypal_subscription_id=paypal_subscription_id,
            )
            Transaction.objects.create(
                user=user,
                subscription=subscription,
                amount=plan.price * number_of_cameras,
                transaction_id=paypal_subscription_id,
            )
            return Response(
                SubscriptionOutSerializer(subscription).data,
                status=status.HTTP_201_CREATED,
            )
        except DatabaseError as e:
            return Response(
                {"error": f"Failed to create subscription: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _create_subscription(
        self,
        user: User,
        plan: Plan,
        start_date: datetime,
        end_date: datetime,
        number_of_cameras: int,
        paypal_subscription_id: str,
    ):
        return Subscription.objects.create(
            user=user,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            number_of_cameras=number_of_cameras,
            paypal_subscription_id=paypal_subscription_id,
        )

    def _create_transaction(
        self,
        user: User,
        subscription: Subscription,
        plan: Plan,
        number_of_cameras: int,
        transaction_id: str,
    ):
        return Transaction.objects.create(
            user=user,
            subscription=subscription,
            amount=plan.price * number_of_cameras,
            transaction_id=transaction_id,
        )


class SubscriptionDetailView(generics.RetrieveAPIView):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionOutSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)


class TransactionListView(generics.ListAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)


class TransactionDetailView(generics.RetrieveAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)
