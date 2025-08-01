from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db import models
from django.contrib.auth.models import User
from .models import ProductAnalysis

class ProductAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAnalysis
        fields = '__all__'
        read_only_fields = ['user', 'extracted_text', 'toxic_score', 'toxic_ingredients', 'created_at']
