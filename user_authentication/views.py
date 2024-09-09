from token import AWAIT
from typing import List
import boto3
from django.contrib.auth import login
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework import serializers
from knox.views import (
    LoginView as KnoxLoginView,
    LogoutView as KnoxLogoutView,
    LogoutAllView as KnoxLogoutAllView,
)
from drf_spectacular.utils import extend_schema, inline_serializer, extend_schema_view
from drf_spectacular.types import OpenApiTypes
from .models import (
    User,
    OTP,
    UserAccess,
    TemporaryUserUpdateData,
)
from .serializers import (
    LoginOutSerializer,
    LogoutSerializer,
    NotificationSerializer,
    PasswordResetSerializer,
    PhoneOTPSerializer,
    UserInSerializer,
    UserOutSerializer,
    UserUpdateInSerializer,
    UserUpdateOutSerializer,
    EmailAuthTokenSerializer,
    ForgotPasswordSerializer,
    PasswordUpdateSerializer,
    EmailSerializer,
    EmailOTPSerializer,
    UserAccessSerializer,
)
from .utils import generate_otp
from ISPECO_Core.settings import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
)
from twilio.rest import Client
from ISPECO_Core.sms_handler import SnsWrapper, logger


class SendEmailOTPView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = EmailSerializer

    @extend_schema(
        request=EmailSerializer,
        responses={status.HTTP_200_OK: OpenApiTypes.STR, 400: OpenApiTypes.STR},
        description="Send an OTP to the user's email address using the email set as DEFAULT_FROM_EMAIL in the settings as the sender.",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            otp = generate_otp()
            try:
                otp_obj = OTP.objects.get(email=email)
            except OTP.DoesNotExist:
                otp_obj = OTP.objects.create(email=email, otp=otp)
            else:
                if otp_obj.is_eligible_for_renewal():
                    otp = otp_obj.renew()
                else:
                    return Response(
                        {"message": "Please wait before requesting a new OTP"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            # Send OTP to user's email
            self.send_otp_mail(email, otp)
            return Response(
                {"message": "OTP sent to your email address"}, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def send_otp_mail(self, email, otp):
        subject = "OTP for ISPECO email verification"
        html_message = render_to_string("otp_email.html", {"otp_code": otp})
        plain_message = strip_tags(html_message)
        to = email
        print(f"Sending OTP email to {to}")
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=None,
            recipient_list=[to],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"OTP email sent to {to}")


class VerifyEmailOTPView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = EmailOTPSerializer

    @extend_schema(
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="VerifyEmailOTPResponse",
                fields={"message": serializers.CharField()},
            ),
            status.HTTP_400_BAD_REQUEST: inline_serializer(
                name="VerifyEmailOTPErrorResponse",
                fields={"message": serializers.CharField()},
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            otp = serializer.validated_data["otp"]
            try:
                otp_obj = OTP.objects.get(email=email, otp=otp)
            except OTP.DoesNotExist:
                return Response(
                    {"message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST
                )
            if otp_obj.is_valid():
                otp_obj.is_verified = True
                otp_obj.save(update_fields=["_is_verified"])
                return Response(
                    {"message": "OTP verified successfully"}, status=status.HTTP_200_OK
                )
            return Response(
                {"message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SignupView(generics.GenericAPIView):
    """
    View for user signup.

    This view allows users to sign up by providing their username and email.
    Upon successful signup, a new user will be created and a success response will be returned.

    Methods:
        post(request, *args, **kwargs): Handles the POST request for user signup.

    Attributes:
        serializer_class: The serializer class used for validating and deserializing the request data.
        permission_classes: The permission classes applied to the view.

    """

    serializer_class = UserInSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=UserInSerializer,
        responses={
            status.HTTP_201_CREATED: OpenApiTypes.STR,
            400: OpenApiTypes.STR,
        },
        description="Validate the user's email address, and create a new user.",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {"message": "User created successfully"}, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(KnoxLoginView):
    """
    View for user login.

    This view allows users to authenticate and log in to the system.
    It inherits from the KnoxLoginView class and overrides the post method
    to handle the login functionality.

    Attributes:
        permission_classes (tuple): A tuple of permission classes that
            determine who can access this view. In this case, it allows
            any user to access the view.

    Methods:
        post(request, format=None): Handles the HTTP POST request for user login.
            It validates the authentication token, logs in the user, and returns
            the response from the parent class's post method.

    """

    permission_classes = (permissions.AllowAny,)
    serializer_class = EmailAuthTokenSerializer

    @extend_schema(
        request=EmailAuthTokenSerializer,
        responses={
            status.HTTP_200_OK: LoginOutSerializer,
            400: OpenApiTypes.STR,
            401: OpenApiTypes.STR,
        },
        description="Authenticate the user and log in to the system. The user must have a verified email address.",
    )
    def post(self, request, format=None):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        return super(LoginView, self).post(request, format=None)


class UserView(generics.RetrieveAPIView):
    """
    View for retrieving user details.

    This view allows users to retrieve their own details after authentication.
    It inherits from the RetrieveAPIView class and overrides the get_object method
    to return the authenticated user.

    Attributes:
        permission_classes (tuple): A tuple of permission classes that
            determine who can access this view. In this case, it requires
            the user to be authenticated.

    Methods:
        get_object(): Retrieves the authenticated user object.

    """

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserOutSerializer

    @extend_schema(
        responses={status.HTTP_200_OK: UserOutSerializer},
        description="Retrieve the details of the authenticated user.",
    )
    def get_object(self):
        return self.request.user


class UpdateUserView(generics.GenericAPIView):
    """
    View for updating user details.

    This view allows users to update their own details after authentication.
    It inherits from the GenericAPIView class and overrides the patch method
    to handle the update functionality.

    Attributes:
        permission_classes (tuple): A tuple of permission classes that
            determine who can access this view. In this case, it requires
            the user to be authenticated.
        serializer_class (class): The serializer class used for validating
            and deserializing input, and for serializing output.

    Methods:
        patch(request, *args, **kwargs): Handles the HTTP PATCH request for updating user details.
            It validates the request data, updates the user details, and returns the response.
    """

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserUpdateInSerializer

    @extend_schema(
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="UserUpdateResponse",
                fields={
                    "data": UserUpdateOutSerializer,
                    "message": serializers.CharField(),
                },
            ),
            status.HTTP_400_BAD_REQUEST: inline_serializer(
                name="UserUpdateErrorResponse",
                fields={"message": serializers.CharField()},
            ),
        },
        description="Partially update the details of the authenticated user.",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user, data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        phone_number = validated_data.get("phone_number")

        try:
            temp_obj = TemporaryUserUpdateData.objects.get(user=request.user)
            if temp_obj.is_expired() is False:
                return Response(
                    {"message": "User data update already in progress"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                temp_obj.delete()
                return self.handle_temp_data(self.request.user, validated_data)
        except TemporaryUserUpdateData.DoesNotExist:
            return self.handle_temp_data(self.request.user, validated_data)

    @extend_schema(
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="UserUpdateResponse",
                fields={
                    "data": UserUpdateOutSerializer,
                    "message": serializers.CharField(),
                },
            ),
            status.HTTP_400_BAD_REQUEST: inline_serializer(
                name="UserUpdateErrorResponse",
                fields={"message": serializers.CharField()},
            ),
        },
        description="Partially update the details of the authenticated user.",
    )
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if "phone_number" in validated_data:
            return Response(
                {"message": "Phone number cannot be updated from this endpoint"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def send_otp(self, phone_number, validated_data) -> Response:
        otp = generate_otp()
        try:
            otp_obj = OTP.objects.get(phone_number=phone_number)
            if not otp_obj.is_eligible_for_renewal():
                return Response(
                    {"message": "Please wait before requesting a new OTP"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            otp = otp_obj.renew()
        except OTP.DoesNotExist:
            OTP.objects.create(phone_number=phone_number, otp=otp)

        client = boto3.client(
            "sns",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
        sns_wrapper = SnsWrapper(client)
        try:
            # message = client.messages.create(
            #     from_=TWILIO_PHONE_NUMBER,
            #     to=str(phone_number),
            #     body=f"Your OTP is {otp}",
            # )
            response = sns_wrapper.publish_text_message(
                str(phone_number), f"Your OTP is {otp}"
            )
            logger.info(f"OTP sent to {phone_number} - {response}")
            # print(f"OTP sent to {phone_number} - {message.sid}")
            validated_data["phone_number"] = str(phone_number)
            return Response(
                {
                    "data": validated_data,
                    "message": "OTP sent as text to phone number, verify to save data",
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            print(f"Error sending OTP: {str(e)}")
            return Response(
                {"message": "Error sending OTP"}, status=status.HTTP_400_BAD_REQUEST
            )

    def handle_temp_data(self, user, validated_data) -> Response:
        phone_number = validated_data.get("phone_number")
        TemporaryUserUpdateData.objects.create(user=self.request.user, **validated_data)
        return self.send_otp(phone_number, validated_data)


class VerifyPhoneOTPView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = PhoneOTPSerializer

    def put(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]
        otp = serializer.validated_data["otp"]
        try:
            otp_obj = OTP.objects.get(phone_number=phone_number, otp=otp)
        except OTP.DoesNotExist:
            return Response(
                {"message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST
            )
        if otp_obj.is_valid():
            try:
                temp_data = TemporaryUserUpdateData.objects.get(
                    user=self.request.user, phone_number=phone_number
                )
                serializer = UserUpdateInSerializer(
                    request.user, data=temp_data.__dict__
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
            except TemporaryUserUpdateData.DoesNotExist:
                return Response(
                    {"message": "No user data update found for this phone number"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            temp_data.delete()
            otp_obj.is_verified = True
            otp_obj.save(update_fields=["_is_verified"])
            return Response(
                {
                    "message": "OTP verified successfully, user data saved",
                    "user": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response({"message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)


class UserPasswordView(generics.GenericAPIView):
    """
    View for updating user password.

    This view allows users to update their password after authentication.
    It inherits from the GenericAPIView class and overrides the put method
    to handle the password update functionality.

    Attributes:
        permission_classes (tuple): A tuple of permission classes that
            determine who can access this view. In this case, it requires
            the user to be authenticated.

    Methods:
        put(request, *args, **kwargs): Handles the HTTP PUT request for updating user password.
            It validates the request data, updates the user password, and returns the response.

    """

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = PasswordUpdateSerializer

    @extend_schema(
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="PasswordUpdateResponse",
                fields={"detail": serializers.CharField()},
            )
        },
        description="Update the password of the authenticated user.",
    )
    def put(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Password updated successfully. Logged out of all clients."},
            status=status.HTTP_200_OK,
        )


class ForgotPasswordView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ForgotPasswordSerializer

    @extend_schema(
        request=ForgotPasswordSerializer,
        responses={
            status.HTTP_200_OK: OpenApiTypes.STR,
            400: OpenApiTypes.STR,
        },
        description="Send a password reset link to the user's email address using the email set as DEFAULT_FROM_EMAIL in the settings as the sender.",
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token = user.generate_password_reset_token()
            reset_link = request.build_absolute_uri(
                reverse("password_reset", kwargs={"token": token})
            )
            user.send_password_reset_email(reset_link)
            return Response(
                "Password reset link sent to your email address",
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetView(generics.GenericAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = PasswordResetSerializer

    @extend_schema(
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="PasswordResetResponse", fields={"token": serializers.CharField()}
            ),
            400: OpenApiTypes.STR,
        },
        description="Check if the password reset token specified in the URL is valid and return the token if it is valid.",
    )
    def get(self, request, *args, **kwargs):
        token = kwargs.get("token")
        try:
            user = User.objects.get(password_reset_token=token)
        except User.DoesNotExist:
            return Response(
                {"message": "Invalid password reset token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.is_password_reset_token_valid():
            return Response(
                {"token": token},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"message": "Invalid password reset token"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @extend_schema(
        request=PasswordResetSerializer,
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="PasswordResetResponsePost",
                fields={"message": serializers.CharField()},
            ),
            400: inline_serializer(
                name="PasswordResetResponseError",
                fields={"message": serializers.CharField()},
            ),
        },
        description="Reset the user's password using the password reset token specified in the URL and update the user's password.",
    )
    def post(self, request, *args, **kwargs):
        token = kwargs.get("token")
        try:
            user = User.objects.get(password_reset_token=token)
        except User.DoesNotExist:
            return Response(
                {"message": "Invalid password reset token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.is_password_reset_token_valid():
            serializer = self.get_serializer(user, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(user)
            user.password_reset_token = None
            user.password_reset_token_created_at = None
            user.save()
            return Response(
                {"message": "Password reset successfully"}, status=status.HTTP_200_OK
            )
        return Response(
            {"message": "Invalid password reset token"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class UserAccessListCreateView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserAccessSerializer

    def get(self, request, *args, **kwargs):
        owner = request.user
        user_accesses: List[UserAccess] = owner.accesses.all()
        data = {
            "user_accesses": [
                {
                    "id": user_access.id,
                    "user_full_name": user_access.user.full_name,
                    "user_email": user_access.user.email,
                    "user_phone_number": user_access.user.phone_number,
                    "user_role": user_access.user_role,
                    "camera_access": user_access.camera_access,
                    "notification_access": user_access.notification_access,
                }
                for user_access in user_accesses
            ]
        }
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user_access = serializer.save()
            data = {
                "id": user_access.id,
                "user_full_name": user_access.user.full_name,
                "user_email": user_access.user.email,
                "user_phone_number": user_access.user.phone_number,
                "user_role": user_access.user_role,
                "camera_access": user_access.camera_access,
                "notification_access": user_access.notification_access,
            }
            return Response(data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserAccessRetrieveUpdateDestroyView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserAccessSerializer

    def get(self, request, *args, **kwargs):
        owner = request.user
        user_access_id = kwargs.get("id")
        try:
            user_access = owner.accesses.get(id=user_access_id)
        except UserAccess.DoesNotExist:
            return Response(
                {"message": "User access not found"}, status=status.HTTP_404_NOT_FOUND
            )
        data = {
            "id": user_access.id,
            "user_full_name": user_access.user.full_name,
            "user_email": user_access.user.email,
            "user_phone_number": user_access.user.phone_number,
            "user_role": user_access.user_role,
            "camera_access": user_access.camera_access,
            "notification_access": user_access.notification_access,
        }
        return Response(data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        owner = request.user
        user_access_id = kwargs.get("id")
        try:
            user_access = owner.accesses.get(id=user_access_id)
        except UserAccess.DoesNotExist:
            return Response(
                {"message": "User access not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(user_access, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        data = {
            "id": user_access.id,
            "user_full_name": user_access.user.full_name,
            "user_email": user_access.user.email,
            "user_phone_number": user_access.user.phone_number,
            "user_role": user_access.user_role,
            "camera_access": user_access.camera_access,
            "notification_access": user_access.notification_access,
        }
        return Response(data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        owner = request.user
        user_access_id = kwargs.get("id")
        try:
            user_access = owner.accesses.get(id=user_access_id)
        except UserAccess.DoesNotExist:
            return Response(
                {"message": "User access not found"}, status=status.HTTP_404_NOT_FOUND
            )
        user_access.delete()
        return Response(
            {"message": "User access deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class NotificationListView(generics.ListAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return self.request.user.notifications.all()


class NotificationRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return self.request.user.notifications.all()

    def get_object(self):
        queryset = self.get_queryset()
        obj = generics.get_object_or_404(queryset, pk=self.kwargs.get("pk"))
        return obj


class NotificationCreateView(generics.CreateAPIView):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = NotificationSerializer

    def perform_create(self, serializer):
        serializer.save()


@extend_schema_view(
    post=extend_schema(
        responses={status.HTTP_204_NO_CONTENT: OpenApiTypes.NONE},
        description="Log out the user",
    )
)
class LogoutView(KnoxLogoutView, generics.GenericAPIView):
    serializer_class = LogoutSerializer


@extend_schema_view(
    post=extend_schema(
        responses={status.HTTP_204_NO_CONTENT: OpenApiTypes.NONE},
        description="Log out the user from all devices",
    )
)
class LogoutAllView(KnoxLogoutAllView, generics.GenericAPIView):
    serializer_class = LogoutSerializer
