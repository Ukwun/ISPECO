from multiprocessing import context
from django.utils import timezone
from django.core.validators import RegexValidator, URLValidator
from rest_framework import serializers

from user_authentication.models import User
from .models import Plan, Subscription, Transaction
from phonenumber_field.serializerfields import PhoneNumberField


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = "__all__"


class CardSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=300)
    number = serializers.CharField(max_length=19)
    security_code = serializers.CharField(max_length=4)
    expiry_date = serializers.DateField(format="%m/%y", input_formats=["%m/%y"])
    state_province = serializers.CharField(max_length=300)
    city_town = serializers.CharField(max_length=120)
    postal_code = serializers.CharField(max_length=60)
    country_code = serializers.CharField(
        max_length=2, validators=[RegexValidator(r"^([A-Z]{2}|C2)$")]
    )

    def validate_expiry_date(self, value):
        # Check if the expiry date is in the future
        if value < timezone.now().date():
            raise serializers.ValidationError("Card has expired")
        return value


class SubscriptionInSerializer(serializers.Serializer):
    card = CardSerializer(required=False, allow_null=True)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    email = serializers.EmailField(required=False, allow_null=True)
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.all())
    number_of_cameras = serializers.IntegerField(default=1)
    payment_method = serializers.CharField(max_length=11)

    def validate_payment_method(self, value):
        if value.upper() not in ["CREDIT_CARD", "PAYPAL"]:
            raise serializers.ValidationError("Invalid payment method")
        return value

    def validate_card(self, value):
        if self.initial_data["payment_method"].upper() == "CREDIT_CARD":
            if not value:
                raise serializers.ValidationError("Card details are required")
        return value

    def validate(self, data):
        if data["payment_method"].upper() == "PAYPAL" and "email" not in data:
            raise serializers.ValidationError("Email is required for PayPal payments")
        if data["payment_method"].upper() == "CREDIT_CARD" and "card" not in data:
            raise serializers.ValidationError(
                "Card details are required for credit card payments"
            )

        if data["payment_method"].upper() == "PAYPAL":
            if "card" in data:
                del data["card"]
        if data["payment_method"].upper() == "CREDIT_CARD":
            if "payment_method" in data:
                del data["payment_method"]
        return data


class SubscriptionOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = "__all__"


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = "__all__"
