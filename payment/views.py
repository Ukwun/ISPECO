from datetime import datetime
from drf_spectacular.utils import extend_schema, inline_serializer
from django.shortcuts import redirect
from numpy import number
from requests import HTTPError
from rest_framework import generics, status
from rest_framework import generics, status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from user_authentication.models import User
from .models import (
    Card,
    Plan,
    Subscription,
    TemporarySubscriptionData,
    Transaction,
)
from .serializers import (
    PlanSerializer,
    SubscriptionInSerializer,
    SubscriptionOutSerializer,
    TransactionSerializer,
)
from .paypal_client import PayPalClient
from django.utils import timezone


class PlanListView(generics.ListAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer


class SubscriptionView(generics.GenericAPIView):
    serializer_class = SubscriptionInSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        user = validated_data["user"]
        email = validated_data.get("email")
        plan = validated_data["plan"]
        card = validated_data.get("card")
        number_of_cameras = validated_data["number_of_cameras"]
        payment_method = validated_data["payment_method"]

        return_url = self.request.build_absolute_uri(
            "/api/payment/paypal/subscribe/success/"
        )
        cancel_url = self.request.build_absolute_uri(
            "/api/payment/paypal/subscribe/cancel-payment/"
        )

        try:
            paypal_subscription_id, approval_url = self._process_payment(
                user,
                plan,
                email,
                card,
                number_of_cameras,
                payment_method,
                return_url,
                cancel_url,
            )
        except HTTPError as http_error:
            return Response(
                {"error": "Failed to process payment", "details": str(http_error)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception as e:
            return Response(
                {"error": "Failed to process payment", "details": e.__str__()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if payment_method.upper() == "PAYPAL":
            try:
                TemporarySubscriptionData.objects.create(
                    user=user,
                    plan=plan,
                    number_of_cameras=number_of_cameras,
                    paypal_subscription_id=paypal_subscription_id,
                )
                return redirect(approval_url)
            except Exception as e:
                print(e)
                return Response(
                    {
                        "error": "Failed to save temporary subscription data",
                        "details": str(e),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:
            subscription = Subscription.objects.get(
                paypal_subscription_id=paypal_subscription_id
            )
            return Response(
                {
                    "message": "Subscription activated successfully",
                    "details": {
                        "start_date": subscription.start_date,
                        "end_date": subscription.end_date,
                        "payment_method": subscription.payment_method,
                        "number_of_cameras": subscription.number_of_cameras,
                        "subscription_id": subscription.id,
                        "paypal_subscription_id": subscription.paypal_subscription_id,
                    },
                }
            )

    def _process_payment(
        self,
        user: User,
        plan: Plan,
        email,
        card,
        number_of_cameras,
        payment_method,
        return_url,
        cancel_url,
    ):
        subscriber = {
            "given_name": user.full_name.split(" ")[0],
            "surname": user.full_name.split(" ")[1],
            "email_address": email if email else user.email,
        }

        if payment_method.upper() == "CREDIT_CARD" and card:
            subscriber["card"] = {
                "name": card["name"],
                "number": card["number"],
                "security_code": card["security_code"],
                "expiry": card["expiry_date"].strftime("%Y-%m"),
                "billing_address": {
                    "postal_code": card["postal_code"],
                    "country_code": card["country_code"],
                    "admin_area_1": card["state_province"],
                    "admin_area_2": card["city_town"],
                },
            }

        paypal_client = PayPalClient()
        paypal_subscription = paypal_client.create_subscription(
            plan_id=plan.paypal_plan_id,
            return_url=return_url,
            cancel_url=cancel_url,
            quantity=number_of_cameras,
            payment_method=payment_method,
            subscriber=subscriber,
        )

        paypal_subscription_id = paypal_subscription["id"]

        if paypal_subscription["status"] == "ACTIVE":
            start_date = timezone.now()
            end_date = start_date + timezone.timedelta(
                days=30 if plan.billing_cycle == "monthly" else 365
            )

            try:
                card = self._create_card(user, card)
                subscription = self._create_subscription(
                    user,
                    plan,
                    card,
                    start_date,
                    end_date,
                    number_of_cameras,
                    payment_method,
                    paypal_subscription_id,
                )
                self._create_transaction(
                    user, subscription, plan, number_of_cameras, paypal_subscription_id
                )
            except Exception as e:
                raise Exception("Failed to create subscription") from e

        return paypal_subscription_id, next(
            (
                link["href"]
                for link in paypal_subscription["links"]
                if link["rel"] == "approve"
            ),
            None,
        )

    def _create_card(self, user: User, card_data):
        if Card.objects.filter(user=user, number=card_data["number"]).exists():
            return Card.objects.get(user=user, number=card_data["number"])
        return Card.objects.create(
            user=user,
            name=card_data["name"],
            number=card_data["number"],
            security_code=card_data["security_code"],
            expiry_date=card_data["expiry_date"],
            state_province=card_data["state_province"],
            city_town=card_data["city_town"],
            postal_code=card_data["postal_code"],
            country_code=card_data["country_code"],
        )

    def _create_subscription(
        self,
        user: User,
        plan: Plan,
        card: Card,
        start_date: datetime,
        end_date: datetime,
        number_of_cameras: int,
        payment_method: str,
        paypal_subscription_id: str,
    ):
        return Subscription.objects.create(
            user=user,
            plan=plan,
            card=card,
            payer_email=None,
            start_date=start_date,
            end_date=end_date,
            number_of_cameras=number_of_cameras,
            payment_method=payment_method,
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


# Paypal return and view
class PayPalReturnView(generics.GenericAPIView):

    @extend_schema(
        request=None,
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="PaypalReturnViewResponse",
                fields={"message": serializers.CharField()},
            ),
            status.HTTP_404_NOT_FOUND: inline_serializer(
                name="PaypalReturnViewError404",
                fields={"error": serializers.CharField()},
            ),
            status.HTTP_403_FORBIDDEN: inline_serializer(
                name="PaypalReturnViewError403",
                fields={"error": serializers.CharField()},
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR: inline_serializer(
                name="PaypalReturnViewError500",
                fields={"error": serializers.CharField()},
            ),
        },
    )
    def get(self, request, *args, **kwargs):
        paypal_subscription_id = request.GET.get("subscription_id")

        try:
            temp_data = TemporarySubscriptionData.objects.get(
                paypal_subscription_id=paypal_subscription_id
            )
        except TemporarySubscriptionData.DoesNotExist:
            return Response(
                {"error": "Subscription data not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        paypal_client = PayPalClient()
        try:
            subscription_details = paypal_client.get_subscription(
                paypal_subscription_id
            )
            payer_email = subscription_details["subscriber"]["email_address"]
            subscription = self._create_subscription(temp_data, payer_email)
            self._create_transaction(temp_data, subscription)

        except Exception as e:
            return Response(
                {"error": f"Failed to create subscription: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        temp_data.delete()
        return Response(
            {
                "message": "Subscription activated successfully",
                "details": {
                    "start_date": subscription.start_date,
                    "end_date": subscription.end_date,
                    "payment_method": subscription.payment_method,
                    "number_of_cameras": subscription.number_of_cameras,
                    "subscription_id": subscription.id,
                    "paypal_subscription_id": subscription.paypal_subscription_id,
                },
            }
        )

    def _create_subscription(
        self, temp_data: TemporarySubscriptionData, payer_email: str
    ):
        plan = temp_data.plan
        start_date = timezone.now()
        end_date = start_date + timezone.timedelta(
            days=30 if plan.billing_cycle == "monthly" else 365
        )

        return Subscription.objects.create(
            user=temp_data.user,
            plan=plan,
            card=None,
            start_date=start_date,
            end_date=end_date,
            payer_email=payer_email,
            number_of_cameras=temp_data.quantity,
            payment_method="paypal",
            paypal_subscription_id=temp_data.paypal_subscription_id,
        )

    def _create_transaction(
        self, temp_data: TemporarySubscriptionData, subscription: Subscription
    ):
        plan = temp_data.plan
        quantity = temp_data.quantity

        Transaction.objects.create(
            user=temp_data.user,
            subscription=subscription,
            amount=plan.price * quantity,
            transaction_id=temp_data.paypal_subscription_id,
        )


class PayPalCancelView(generics.GenericAPIView):

    @extend_schema(
        request=None,
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="PayPalCancelViewResponse",
                fields={"message": serializers.CharField()},
            ),
            status.HTTP_404_NOT_FOUND: inline_serializer(
                name="PayPalCancelViewError404",
                fields={"error": serializers.CharField()},
            ),
            status.HTTP_403_FORBIDDEN: inline_serializer(
                name="PayPalCancelViewError403",
                fields={"error": serializers.CharField()},
            ),
        },
    )
    def get(self, request, *args, **kwargs):
        paypal_subscription_id = request.GET.get("subscription_id")

        try:
            temp_data = TemporarySubscriptionData.objects.get(
                paypal_subscription_id=paypal_subscription_id
            )
        except TemporarySubscriptionData.DoesNotExist:
            return Response(
                {"error": "Subscription data not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        temp_data.delete()
        return Response(
            {"message": "Subscription cancelled successfully"},
            status=status.HTTP_200_OK,
        )


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
