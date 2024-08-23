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


class SubscriptionInSerializer(serializers.Serializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.all())
    number_of_cameras = serializers.IntegerField(default=1)
    paypal_subscription_id = serializers.CharField(max_length=100)

    def validate_paypal_subscription_id(self, value):
        # Check if the subscription ID is unique
        if Subscription.objects.filter(paypal_subscription_id=value).exists():
            raise serializers.ValidationError("Subscription ID already exists")
        return value


class SubscriptionOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = "__all__"


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = "__all__"
