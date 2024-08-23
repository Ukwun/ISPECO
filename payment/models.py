from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from .paypal_client import PayPalClient
from user_authentication.models import User


class Product(models.Model):
    name = models.CharField(max_length=300, unique=True)
    description = models.TextField()
    paypal_product_id = models.CharField(
        max_length=50, blank=True, null=True, editable=False
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        paypal_client = PayPalClient()
        # Check if the product is new
        is_new = not self.pk

        if is_new and not self.paypal_product_id:
            try:
                paypal_product = paypal_client.create_product(
                    name=self.name, description=self.description
                )
                self.paypal_product_id = paypal_product.get("id")
            except Exception as e:
                raise ValidationError(f"Failed to create product in PayPal: {str(e)}")
        elif not is_new and self.paypal_product_id:
            # Update the product in PayPal
            try:
                paypal_client.update_product(
                    product_id=self.paypal_product_id,
                    description=self.description,
                )
            except Exception as e:
                raise ValidationError(f"Failed to update product in PayPal: {str(e)}")

        with transaction.atomic():
            super().save(*args, **kwargs)


class Plan(models.Model):
    PLAN_TIERS = [
        ("basic", "Basic"),
        ("standard", "Standard"),
        ("premium", "Premium"),
    ]
    BILLING_FREQUENCIES = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    name = models.CharField(max_length=50, choices=PLAN_TIERS)
    description = models.TextField()
    billing_cycle = models.CharField(max_length=50, choices=BILLING_FREQUENCIES)
    price = models.DecimalField(max_digits=30, decimal_places=2)
    setup_fee = models.DecimalField(max_digits=30, decimal_places=2)
    paypal_plan_id = models.CharField(
        max_length=50, blank=True, null=True, editable=False
    )
    currency = models.CharField(max_length=3, default="USD")
    auto_renew = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name.title()} ({self.billing_cycle.upper()})"

    def save(self, *args, **kwargs):
        paypal_client = PayPalClient()
        is_new = not self.pk
        old_instance = None

        if not is_new:
            old_instance = Plan.objects.get(pk=self.pk)

        if is_new and not self.paypal_plan_id:
            try:
                paypal_plan = paypal_client.create_plan(
                    name=self.name,
                    description=self.description,
                    billing_cycle=self.billing_cycle,
                    price=self.price,
                    setup_fee=self.setup_fee,
                    currency=self.currency,
                    product_id=self.product.paypal_product_id,
                )
                self.paypal_plan_id = paypal_plan.get("id")
            except Exception as e:
                raise ValidationError(f"Failed to create plan in PayPal: {str(e)}")
        else:
            # Only update if certain fields have changed
            if old_instance:
                updates = {}
                if old_instance.description != self.description:
                    updates["description"] = self.description
                if old_instance.name != self.name:
                    updates["name"] = self.name
                if old_instance.setup_fee != self.setup_fee:
                    updates["setup_fee"] = self.setup_fee
                if old_instance.auto_renew != self.auto_renew:
                    updates["auto_renew"] = self.auto_renew

                if updates:
                    try:
                        paypal_client.update_plan(
                            plan_id=self.paypal_plan_id, **updates
                        )
                    except Exception as e:
                        raise ValidationError(
                            f"Failed to update plan in PayPal: {str(e)}"
                        )

        with transaction.atomic():
            super().save(*args, **kwargs)


class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    number_of_cameras = models.IntegerField(default=1)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    paypal_subscription_id = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.user.email} - {self.plan.name.title()} ({self.start_date})"


class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    transaction_id = models.CharField(max_length=100)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Tnx ID: {self.transaction_id} - {self.user.email} - {self.amount} {self.subscription.plan.currency.upper()}"
