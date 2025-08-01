from django.shortcuts import render
from django.conf import settings

# django validations and auth methods
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.hashers import check_password

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

# rest framework dependencies
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

# swagger documentation libs
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

# other requirements
import datetime, os
import uuid
import environ
import re, json
from PIL import Image
import requests
from io import BytesIO

# models, serializers and other dependencies
from django.contrib.auth.models import User
from .models import ProductAnalysis
from .serializers import ProductAnalysisSerializer
from .services.ai_services import analyse_ingredients_with_gemini, extract_ingredients
from user_app.views import isTokenValid, getUserByEmail, getUserByID, getUserProfile


class GetAnalyse(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  
    @swagger_auto_schema(
        operation_description="Upload image file",
        manual_parameters=[
            openapi.Parameter(
                name='image',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description='Image file to upload',
                required=True
            )
        ],
        responses={
            200: openapi.Response(description="Image uploaded")
        }
    )

    def post(self, request):

        token = request.COOKIES.get("jwt")
        payload = isTokenValid(token=token)
        user = getUserByID(payload)
        profile = getUserProfile(user.id)

        image_file = request.FILES.get("image")
        if not image_file:
            return Response({"error": "image dosyası gereklidir."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # OCR işlemi
            extracted_text = extract_ingredients(image_file=image_file)

            sensivities = profile.sensitivity if profile.sensitivity else "None" 
            # ask Gemini
            llm_result = analyse_ingredients_with_gemini(extracted_text=extracted_text, user_sensitivities=sensivities)
            toxic_score = llm_result.get("toksisite_skoru", 5)
            toxic_ingredients = llm_result.get("tehlikeli_maddeler", [])
            general_review = llm_result.get("genel_aciklama", "")

            if not llm_result:
                return Response(
                    {"error":"System can't produce analyse, try again."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            ext = os.path.splitext(image_file.name)[-1]
            filename = f"{uuid.uuid4()}{ext}"
            path = f"uploads/product_images/{filename}"
            full_path = default_storage.save(path, ContentFile(image_file.read()))
            image_url = request.build_absolute_uri(default_storage.url(full_path))

            # save analysis
            analysis = ProductAnalysis.objects.create(
                user=user,
                image_url=image_url,
                extracted_text=extracted_text,
                toxic_score=toxic_score,
                toxic_ingredients=toxic_ingredients,
                general_review=general_review
            )
            serializer = ProductAnalysisSerializer(analysis)
            data = serializer.data  

            response_content = {
                "user"              : data["user"],
                "toxic_score"       : data["toxic_score"],
                "toxic_ingredients" : data["toxic_ingredients"],
                "general_review"    : data["general_review"],
                "extracted_text"    : data["extracted_text"],
                "image_url"         : data["image_url"],
                "created_at"        : data["created_at"],
            }
            return Response(response_content, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





# ask Gemini
# llm_result = analyse_ingredients_with_gemini(extracted_text)

# # parse response
# score_match = re.search(r"skor[:\s]*([0-9.]+)", llm_result.lower())
# toxic_score = float(score_match.group(1)) if score_match else 0.5

# lines = llm_result.split('\n')
# toxic_ingredients = [line.strip() for line in lines if "-" in line or "•" in line]
