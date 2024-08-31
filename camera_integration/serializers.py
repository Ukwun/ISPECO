from typing import Any
from django.core.validators import URLValidator
from rest_framework import serializers
from .models import Camera


class CameraSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    stream_url = serializers.CharField(
        validators=[URLValidator(schemes=["rtsp", "http", "https", "rtmp", "ftp"])],
    )

    class Meta:
        model = Camera
        exclude = ("encrypted_password", "encrypted_url")

    def create(self, validated_data: dict[str, Any]) -> Camera:
        password = validated_data.pop("password")
        stream_url = validated_data.pop("stream_url")
        camera = Camera.objects.create(**validated_data)
        camera.password = password
        camera.stream_url = stream_url
        camera.save()
        return camera

    def update(self, instance: Camera, validated_data: dict[str, Any]) -> Camera:
        password = validated_data.pop("password", None)
        stream_url = validated_data.pop("stream_url", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.password = password
        if stream_url:
            instance.stream_url = stream_url

        instance.save()
        return instance


class AuthenticationDetailsSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
