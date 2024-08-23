from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .forms import ProductAddForm, ProductAdminForm, PlanAddForm, PlanAdminForm

from .models import Plan, Subscription, Transaction, Product

admin.site.register(Subscription)
admin.site.register(Transaction)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "paypal_product_id")
    search_fields = ("name",)

    def get_form(self, request, obj=None, **kwargs):
        if obj:
            self.form = ProductAdminForm
        else:
            self.form = ProductAddForm
        return super(ProductAdmin, self).get_form(request, obj, **kwargs)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "product", "paypal_plan_id")
    search_fields = ("name",)

    def get_form(self, request, obj=None, **kwargs):
        if obj:
            self.form = PlanAdminForm
        else:
            self.form = PlanAddForm
        return super(PlanAdmin, self).get_form(request, obj, **kwargs)
