from typing import Any, Dict, Union, Optional
import requests

from ISPECO_Core.settings import PAYPAL_CLIENT_ID, PAYPAL_SECRET


class PayPalClient:
    """
    A class representing a PayPal client.

    This class provides methods to interact with the PayPal API for creating products, plans, subscriptions, and more.

    Attributes:
        client_id (str): The client ID for the PayPal API.
        secret (str): The secret key for the PayPal API.
        base_url (str): The base URL for the PayPal API.

    Methods:
        get_access_token: Retrieves the access token for making API requests.
        create_product: Creates a new product in the PayPal catalog.
        create_plan: Creates a new billing plan for a product.
        update_plan_auto_renewal: Updates the auto-renewal setting for a billing plan.
        create_subscription: Creates a new subscription for a billing plan.
        get_subscription: Retrieves information about a subscription.

    """

    def __init__(self):
        self.client_id = PAYPAL_CLIENT_ID
        self.secret = PAYPAL_SECRET
        self.base_url = "https://api-m.sandbox.paypal.com"  # Use 'https://api-m.paypal.com' for production

    def get_access_token(self) -> str:
        """
        Retrieves the access token for making API requests.

        Returns:
            str: The access token.

        """
        url = f"{self.base_url}/v1/oauth2/token"
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}
        response = requests.post(
            url, headers=headers, data=data, auth=(self.client_id, self.secret)
        )
        response_data = response.json()
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        return response_data["access_token"]

    def create_product(self, name: str, description: str) -> Dict:
        """
        Creates a new product in the PayPal catalog.

        Args:
            name (str): The name of the product.
            description (str): The description of the product.

        Returns:
            dict: The response data containing information about the created product.

        """
        url = f"{self.base_url}/v1/catalogs/products"
        access_token = self.get_access_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        data = {
            "name": name,
            "description": description,
            "type": "SERVICE",
            "category": "SOFTWARE",
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        return response.json()

    def update_product(self, product_id: str, description: str) -> Dict:
        url = f"{self.base_url}/v1/catalogs/products/{product_id}"
        access_token = self.get_access_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        data = [
            {
                "op": "replace",
                "path": "/description",
                "value": description,
            }
        ]
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        return {"message": "Product updated successfully."}

    def create_plan(
        self,
        product_id: str,
        name: str,
        description: str,
        price: Union[int, float],
        setup_fee: Union[int, float],
        currency: str,
        billing_cycle: str,
    ) -> Dict:
        """
        Creates a new billing plan for a product.

        Args:
            product_id (str): The ID of the product.
            name (str): The name of the plan.
            description (str): The description of the plan.
            price (float): The price of the plan.
            currency (str): The currency code (e.g., 'USD') of the plan.
            billing_cycle (str): The billing cycle of the plan ('monthly' or 'yearly').

        Returns:
            dict: The response data containing information about the created plan.

        """
        url = f"{self.base_url}/v1/billing/plans"
        access_token = self.get_access_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        if currency == "ZAR":
            price = round(
                price * 0.0561, 2
            )  # Convert to ZAR PayPal's internal currency
            setup_fee = round(
                setup_fee * 0.0561, 2
            )  # Convert to ZAR PayPal's internal currency
        billing_frequency = "MONTH" if billing_cycle == "monthly" else "YEAR"
        data = {
            "product_id": product_id,
            "name": name,
            "description": description,
            "billing_cycles": [
                {
                    "frequency": {
                        "interval_unit": billing_frequency,
                        "interval_count": 1,
                    },
                    "tenure_type": "REGULAR",
                    "sequence": 1,
                    "total_cycles": 0,
                    "pricing_scheme": {
                        "fixed_price": {"value": str(price), "currency_code": currency}
                    },
                }
            ],
            "quantity_supported": True,
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "setup_fee": {"value": str(setup_fee), "currency_code": currency},
                "setup_fee_failure_action": "CONTINUE",
                "payment_failure_threshold": 3,
            },
            "taxes": {"percentage": "0", "inclusive": False},
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        return response.json()

    def update_plan(
        self,
        plan_id: str,
        setup_fee: Union[int, float, None] = None,
        description: Optional[str] = None,
        name: Optional[str] = None,
        auto_renew: Optional[bool] = None,
    ) -> Dict:
        url = f"{self.base_url}/v1/billing/plans/{plan_id}"
        access_token = self.get_access_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        setup_fee = round(setup_fee * 0.0561, 2) if setup_fee is not None else None
        # Create a dictionary of the optional parameters
        updates = {
            "/payment_preferences/setup_fee": (
                str(setup_fee) if setup_fee is not None else None
            ),
            "/description": description,
            "/name": name,
            "/payment_preferences/auto_bill_outstanding": auto_renew,
        }

        # Use list comprehension to filter out None values and create the patch data
        data = [
            {"op": "replace", "path": path, "value": value}
            for path, value in updates.items()
            if value is not None
        ]

        # Send the PATCH request
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()

        # Return the response since the API does not return any data
        return {"message": "Plan updated successfully."}

    def create_subscription(
        self,
        plan_id: str,
        return_url: str,
        cancel_url: str,
        quantity: int,
        payment_method: str = "PAYPAL",
        subscriber: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        Creates a new subscription for a billing plan.

        Args:
            plan_id (str): The ID of the billing plan.
            return_url (str): The URL to redirect to after the subscription is created.
            cancel_url (str): The URL to redirect to if the subscription is canceled.
            quantity (int): The quantity of the subscription.
            subscriber (dict): The subscriber information.
            payment_method (str): The payment method for the subscription ('PAYPAL' or 'CREDIT_CARD').

        Returns:
            dict: The response data containing information about the created subscription.

        """
        url = f"{self.base_url}/v1/billing/subscriptions"
        access_token = self.get_access_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        data = {
            "plan_id": plan_id,
            "quantity": str(quantity),
            "application_context": {
                "brand_name": "ISPECO",
                "locale": "en-US",
                "shipping_preference": "NO_SHIPPING",
                "user_action": "SUBSCRIBE_NOW",
                "return_url": return_url,
                "cancel_url": cancel_url,
                "payment_method": {
                    "payer_selected": "PAYPAL",
                    "payee_preferred": "IMMEDIATE_PAYMENT_REQUIRED",
                },
            },
            "subscriber": {
                "name": {
                    "given_name": subscriber["given_name"],
                    "surname": subscriber["surname"],
                },
                "email_address": subscriber["email_address"],
            },
        }

        if payment_method.upper() == "CREDIT_CARD":
            data["subscriber"]["payment_source"] = {
                "card": {
                    "name": subscriber["card"]["name"],
                    "number": subscriber["card"]["number"],
                    "security_code": subscriber["card"]["security_code"],
                    "expiry": subscriber["card"]["expiry"],
                    "billing_address": {
                        "postal_code": subscriber["card"]["billing_address"][
                            "postal_code"
                        ],
                        "country_code": subscriber["card"]["billing_address"][
                            "country_code"
                        ],
                        "admin_area_1": subscriber["card"]["billing_address"][
                            "admin_area_1"
                        ],
                        "admin_area_2": subscriber["card"]["billing_address"][
                            "admin_area_2"
                        ],
                    },
                }
            }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        return response.json()

    def get_subscription(self, subscription_id: str) -> Dict:
        """
        Retrieves information about a subscription.

        Args:
            subscription_id (str): The ID of the subscription.

        Returns:
            dict: The response data containing information about the subscription.

        """
        url = f"{self.base_url}/v1/billing/subscriptions/{subscription_id}"
        access_token = self.get_access_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        return response.json()
