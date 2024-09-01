from django.conf import settings
from django.db import models
from user_authentication.models import User

from cryptography.fernet import Fernet


class Camera(models.Model):
    """
    Represents a camera model.
    Attributes:
        user (ForeignKey): The user associated with the camera.
        name (CharField): The name of the camera.
        camera_type (CharField): The type of the camera.
        industry_type (CharField): The industry type of the camera.
        environment (CharField): The environment in which the camera is used.
        resolution (CharField): The resolution of the camera.
        brand (CharField): The brand of the camera.
        encrypted_url (BinaryField): The encrypted URL of the camera.
        ip_address (GenericIPAddressField): The IP address of the camera.
        port (IntegerField): The port number of the camera.
        username (CharField): The username for accessing the camera.
        encrypted_password (BinaryField): The encrypted password for accessing the camera.
        address_line_1 (CharField): The address line 1 of the camera's location.
        address_line_2 (CharField): The address line 2 of the camera's location.
        city (CharField): The city of the camera's location.
        zip_code (CharField): The zip code of the camera's location.
        state_province (CharField): The state or province of the camera's location.
        country (CharField): The country of the camera's location.
        date (DateField): The date of installation of the camera.
        time (TimeField): The time of installation of the camera.
        installation_notes (TextField): Any notes related to the camera installation.
    Methods:
        password(self) -> str:
        password(self, value: str) -> None:
        stream_url(self) -> str:
        stream_url(self, value: str) -> None:
        __str__(self) -> str:
            Returns a string representation of the camera.
        save(self, *args, **kwargs):
            Overrides the save method to set the default name if it is not provided.
    """

    CAMERA_ENVIRONMENT_CHOICES = [
        ("indoor", "Indoor"),
        ("outdoor", "Outdoor"),
        ("both", "Both"),
    ]
    CAMERA_TYPE_CHOICES = [
        ("dome", "Dome"),
        ("bullet", "Bullet"),
        ("ptz", "PTZ (Pan-Tilt-Zoom)"),
        ("c_mount", "C-Mount"),
        ("day_night", "Day/Night"),
        ("thermal", "Thermal"),
        ("wireless", "Wireless"),
        ("hd", "High Definition (HD)"),
        ("360", "360-Degree"),
        ("network_ip", "Network/IP"),
    ]
    INDUSTRY_TYPE_CHOICES = [
        ("retail", "Retail"),
        ("restaurant", "Restaurant"),
        ("club", "Club"),
        ("others", "Others"),
    ]
    CAMERA_RESOLUTION_CHOICES = [
        ("1mp", "1MP"),
        ("2mp", "2MP"),
        ("3mp", "3MP"),
        ("4mp", "4MP"),
        ("5mp", "5MP"),
        ("6mp", "6MP"),
        ("7mp", "7MP"),
        ("8mp", "8MP"),
    ]
    CAMERA_BRAND_CHOICES = [
        ("samsumg", "Samsung"),
        ("avigilon", "Avigilon"),
        ("honeywell", "Honeywell"),
        ("axiscommunication", "AxisCommunication"),
        ("panasonic", "Panasonic"),
        ("vivotek", "Vivotek"),
        ("alhuatechnology", "AlhuaTechnology"),
        ("hikvision", "HikVision"),
        ("bosch", "Bosch"),
        ("cp_plus", "CP Plus"),
        ("others", "Others"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cameras")
    name = models.CharField(max_length=255, blank=True, null=True)
    camera_type = models.CharField(max_length=50, choices=CAMERA_TYPE_CHOICES)
    industry_type = models.CharField(max_length=50)
    environment = models.CharField(max_length=50, choices=CAMERA_ENVIRONMENT_CHOICES)
    resolution = models.CharField(max_length=50, choices=CAMERA_RESOLUTION_CHOICES)
    brand = models.CharField(max_length=50, choices=CAMERA_BRAND_CHOICES)
    encrypted_url = models.BinaryField(blank=True, null=True)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField()
    username = models.CharField(max_length=50, blank=True, null=True)
    encrypted_password = models.BinaryField(blank=True, null=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=10)
    state_province = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    installation_notes = models.TextField(blank=True, null=True)

    @property
    def password(self) -> str:
        """
        Decrypts and returns the encrypted password.

        Returns:
            str: The decrypted password.
        """
        fernet = Fernet(settings.FERNET_KEY)
        encrypted_password = bytes(self.encrypted_password)
        if not encrypted_password:
            return ""
        return fernet.decrypt(encrypted_password).decode()

    @password.setter
    def password(self, value: str) -> None:
        """
        Encrypts the given password using Fernet encryption and stores it in the encrypted_password attribute.

        Args:
            value (str): The password to be encrypted.

        Returns:
            None
        """
        fernet = Fernet(settings.FERNET_KEY)
        self.encrypted_password = fernet.encrypt(value.encode())

    @property
    def stream_url(self) -> str:
        """
        Decrypts and returns the encrypted URL.

        Returns:
            str: The decrypted URL.
        """
        fernet = Fernet(settings.FERNET_KEY)
        encrypted_url = bytes(self.encrypted_url)
        if encrypted_url:
            return fernet.decrypt(encrypted_url).decode()
        else:
            return ""

    @stream_url.setter
    def stream_url(self, value: str) -> None:
        """
        Encrypts the given URL using Fernet encryption and stores it in the encrypted_url attribute.

        Args:
            value (str): The URL to be encrypted.

        Returns:
            None
        """
        fernet = Fernet(settings.FERNET_KEY)
        self.encrypted_url = fernet.encrypt(value.encode())

    def __str__(self) -> str:
        return f"{self.brand} {self.camera_type} ({self.pk})"

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = f"{self.brand} {self.camera_type} ({self.pk})"
        super().save(*args, **kwargs)
