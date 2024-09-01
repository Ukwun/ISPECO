from drf_spectacular.utils import extend_schema, inline_serializer
from knox.auth import TokenAuthentication
from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response

from .serializers import (
    AuthenticationDetail,
    CameraSerializer,
    AuthenticationDetailsSerializer,
)
from .models import Camera


class CameraListCreateView(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (TokenAuthentication,)
    serializer_class = CameraSerializer

    def get_queryset(self):
        return Camera.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CameraRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (TokenAuthentication,)
    serializer_class = CameraSerializer
    lookup_field = "id"

    def get_queryset(self):
        return Camera.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)


class CameraAuthenticationDetailsRetrieveView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        responses={
            200: AuthenticationDetailsSerializer,
            403: inline_serializer(
                name="Password403",
                fields={"message": serializers.CharField()},
            ),
            404: inline_serializer(
                name="Password404",
                fields={"message": serializers.CharField()},
            ),
        },
        description="Retrieve the password of a camera specified by ID in the URL.",
    )
    def get(self, request, *args, **kwargs):
        try:
            camera = Camera.objects.get(id=kwargs["id"])
        except Camera.DoesNotExist:
            return Response(
                {"message": "Camera not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if camera.user != request.user:
            return Response(
                {"message": "This user does not have access to this camera"},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = AuthenticationDetail(username=camera.username, password=camera.password)
        serializer = AuthenticationDetailsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CameraStreamUrlView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        responses={
            200: inline_serializer(
                name="Url200",
                fields={"stream_url": serializers.CharField()},
            ),
            403: inline_serializer(
                name="Url403",
                fields={"message": serializers.CharField()},
            ),
            404: inline_serializer(
                name="Url404",
                fields={"message": serializers.CharField()},
            ),
        },
        description="Retrieve the URL of a camera specified by ID in the URL.",
    )
    def get(self, request, *args, **kwargs):
        try:
            camera = Camera.objects.get(id=kwargs["id"])
        except Camera.DoesNotExist:
            return Response(
                {"message": "Camera not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if camera.user != request.user:
            return Response(
                {"message": "This user does not have access to this camera"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response({"stream_url": camera.stream_url}, status=status.HTTP_200_OK)
