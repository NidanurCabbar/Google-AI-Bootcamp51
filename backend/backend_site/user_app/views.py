from django.shortcuts import render
from django.conf import settings

# django validations and auth methods
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.hashers import check_password

# rest framework dependencies
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework.permissions import IsAuthenticated

# swagger documentation libs
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

# other requirements
import datetime, os
import environ
import jwt

# models, serializers and other dependencies
from django.contrib.auth.models import User
from .serializers import UserSerializer, ProfileSerializer
from .models import Profile
env = environ.Env()
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))


def generateToken(user:User)->str:
    """
    Genaretes JWT Token with user id

    Token expires after 60 minutes

    Returns generated jwt token as a string.

    params:
        user: object of the User Model
    """
    payload = {
        "id": user.id,
        "exp": datetime.datetime.now() + datetime.timedelta(minutes=60),
        "iat": datetime.datetime.now()
    }
    # os.environ.get('JWT_SECRET')
    token = jwt.encode(payload, env("JWT_SECRET"), algorithm="HS256")
    return token

def isTokenValid(token:str)-> dict|AuthenticationFailed|NotFound:
    """
    Decodes provided JWT Token to payload.

    If token is valid or provided returns payload, in else case raise NotFound (404) or AuthenticationFailed (401)

    Return param:
        payload : dict {'id', 'exp', 'iat'}

    params:
        token : JWT token as a str  
    """
    if not token:
        raise NotFound("Authentication token is missing.")
    try:
        payload = jwt.decode(token, env("JWT_SECRET"), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed("Invalid or expired token!")
    return payload

def getUserByEmail(email:str) -> User|AuthenticationFailed:
    """
    returns User if there is any user with provided email or raise AuthenticationFailed (401)

    params:
    email : user provided email as str
    """
    user = User.objects.filter(email=email).first()
    if user is None:
        raise AuthenticationFailed("User not found!")
    return user

def getUserByID(payload:dict) -> User|NotFound :
    """
    Returns User with the id provided in payload.

    If there is no User with the ID the raise NotFound (404)

    params:
        payload : Decoded JWT Token as a dict {'id', 'exp', 'iat'}
    """
    user = User.objects.filter(id=payload["id"]).first()
    if not user:
        raise NotFound("User is not found!")
    return user

def getUserProfile(user_id:int) -> Profile|NotFound:
    """
    Returns Profile with the user id provided in params.

    If there is no Profile with the ID the raise NotFound (404)

    params:
        payload : User ID
    """
    profile = Profile.objects.filter(user=user_id).first()
    if not profile:
        raise NotFound("User's profile is not found!")
    return profile


def get_age_category(age: int) -> str:
    if age < 0:
        raise ValueError("Age must be a non-negative integer.")
    elif age < 3:
        return "1"  # Baby-Todler
    elif age < 13:
        return "2"  # Childhood
    elif age < 20:
        return "3"  # Adolescent
    elif age < 35:
        return "4"  # Young Adult
    elif age < 50:
        return "5"  # Middle Adult
    else:
        return "6"  # Old Adults


class RegisterView(APIView):

    @swagger_auto_schema(
        operation_description="User registration endpoint with nested profile data",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Username'),
                'first_name': openapi.Schema(type=openapi.TYPE_STRING, description='User first name'),
                'last_name': openapi.Schema(type=openapi.TYPE_STRING, description='User last name'),
                'email': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL, description='User email'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD, description='User password'),
                'profile': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'bio': openapi.Schema(type=openapi.TYPE_STRING, description='User biography'),
                        'age': openapi.Schema(type=openapi.TYPE_INTEGER, description='User age'),
                        'sensitivity': openapi.Schema(type=openapi.TYPE_STRING, description='User sensitivity information'),
                    },
                    required=['age'],
                    description='Profile details'
                )
            },
            required=['username', 'first_name', 'last_name', 'email', 'password', 'profile'],
            example={
                "username": "aysenur",
                "first_name": "Ayşe",
                "last_name": "Nur",
                "email": "aysenur@example.com",
                "password": "your_password_here",
                "profile": {
                    "bio": "Yeni biyografi",
                    "age": 25,
                    "sensitivity": "Polen"
                }
            }
        ),
        responses={
            201: openapi.Response(
                description="User successfully created",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, description='Success message')
                    },
                    example={"message": "User created successfully"}
                )
            ),
            400: openapi.Response(
                description="Validation error (e.g. username or email already exists)",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING, description='Error message')
                    },
                    example={"error": "Username already exists"}
                )
            )
        }
    )

    def post(self, request):
        data = request.data
        profile_data = data.pop('profile', {})

        # check if the user data is valid
        if User.objects.filter(username=data['username']).exists():
            return Response(
                    {'error': 'Username already exists'}, 
                    status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(email=data['email']).exists():
            return Response(
                    {'error': 'Email already exists'}, 
                    status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer = UserSerializer(data = data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()  

            age = profile_data.get('age')
            if age is None:
                return Response({'error': 'Age is required in profile data'}, status=status.HTTP_400_BAD_REQUEST)

            profile_data['age_category'] = get_age_category(int(age))
            profile_data['user'] = user.id

            profile_serializer = ProfileSerializer(data=profile_data)
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save()
            
        except DjangoValidationError as e:
            return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {           'message': 'User created successfully'}, 
                        status=status.HTTP_201_CREATED
                        )
    

class LoginView(APIView):
    @swagger_auto_schema(
        operation_description="User login endpoint",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Username'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD, description='User password'),
            },
            required=['username', 'password'],
            example={
                'username': 'aysenur',
                'password': 'your_password_here'
            }
        ),
        responses={
            200: openapi.Response(
                description="Successful login",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, description='Success message')
                    },
                    example={'message': 'User logged in successfully'}
                )
            ),
            401: openapi.Response(
                description="Authentication failed due to invalid credentials",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Error detail message')
                    },
                    example={'detail': 'Invalid credentials, try again or please register'}
                )
            )
        }
    )
    
    def post(self, request):

        username = request.data['username']
        password = request.data['password']
        print(username)

        django_user = authenticate(request=request, username=username, password=password) 
        if django_user is None:
            raise AuthenticationFailed("Invalid credentials, try again or please register")
        login(request=request, user=django_user)

        # JWT configuration
        token = generateToken(user= django_user)
        response = Response()
        # cookie set backend only
        response.set_cookie(key="jwt", value=token, httponly=True)
        response.data = {
            "jwt": token,
            'message': 'User logged in successfully',
        }
        response.status_code = status.HTTP_200_OK
        return response


class LogoutView(APIView):
    
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="User logout endpoint, requires authentication",
        responses={
            200: openapi.Response(
                description="Successful logout",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, description='Success message')
                    },
                    example={'message': 'User logged out successfully'}
                )
            ),
            401: openapi.Response(
                description="Unauthorized access",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Authentication error message')
                    },
                    example={'detail': 'Authentication credentials were not provided.'}
                )
            )
        }
    )
    
    def get(self, request):

        response = Response()
        # delete token from cookies
        response.delete_cookie("jwt")
        response.data= {
            "message": "User logged out successfully"
        }
        response.status_code = status.HTTP_200_OK
        # logout with django auth
        logout(request=request)
        return response


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get current authenticated user's profile data",
        responses={
            200: openapi.Response(
                description="User profile retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        # Burada user ve profile serializerdan dönen alanlar kombine edildiği için genel örnek
                        'username': openapi.Schema(type=openapi.TYPE_STRING, description='Username'),
                        'first_name': openapi.Schema(type=openapi.TYPE_STRING, description='First name'),
                        'last_name': openapi.Schema(type=openapi.TYPE_STRING, description='Last name'),
                        'email': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL, description='Email'),
                        'bio': openapi.Schema(type=openapi.TYPE_STRING, description='User bio'),
                        'age': openapi.Schema(type=openapi.TYPE_INTEGER, description='User age'),
                        'age_category': openapi.Schema(type=openapi.TYPE_STRING, description='Age category code'),
                        'sensitivity': openapi.Schema(type=openapi.TYPE_STRING, description='Sensitivity info'),
                        # vb.
                    },
                    example={
                        "username": "aysenur",
                        "first_name": "Ayşe",
                        "last_name": "Nur",
                        "email": "aysenur@example.com",
                        "bio": "Yeni biyografi",
                        "age": 25,
                        "age_category": "4",
                        "sensitivity": "Polen"
                    }
                )
            ),
            401: openapi.Response(
                description="Authentication credentials were not provided",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Authentication error')
                    },
                    example={"detail": "Authentication credentials were not provided."}
                )
            )
        }
    )

    def get(self, request):
        token = request.COOKIES.get("jwt")
        print(token)
        payload = isTokenValid(token=token)
        print(payload)
        user = getUserByID(payload)
        print(user)

        user_serializer = UserSerializer(user)
        profile_serializer = ProfileSerializer(user.profile)
        result = user_serializer.data | profile_serializer.data
        return Response(
                        result,
                        status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_description="Delete the authenticated user and their profile",
        responses={
            200: openapi.Response(
                description="User deleted successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, description='Success message')
                    },
                    example={'message': 'User deleted successfully'}
                )
            ),
            401: openapi.Response(
                description="Unauthorized - Authentication required",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Authentication error')
                    },
                    example={"detail": "Authentication credentials were not provided."}
                )
            )
        }
    )
    
    def delete(self, request):
        token = request.COOKIES.get("jwt")
        payload = isTokenValid(token=token)
        user = getUserByID(payload)

        user.delete()
        return Response(
                {'message': 'User deleted successfully'}, 
                status=status.HTTP_200_OK)


class ProfileEditView(APIView):

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Update current authenticated user's profile and user data",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "username": openapi.Schema(type=openapi.TYPE_STRING, description="Username"),
                "first_name": openapi.Schema(type=openapi.TYPE_STRING, description="First name"),
                "last_name": openapi.Schema(type=openapi.TYPE_STRING, description="Last name"),
                "email": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL, description="Email"),
                "profile": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "bio": openapi.Schema(type=openapi.TYPE_STRING, description="User biography"),
                        "age": openapi.Schema(type=openapi.TYPE_INTEGER, description="User age"),
                        "age_category": openapi.Schema(type=openapi.TYPE_STRING, description="Age category code"),
                        "sensitivity": openapi.Schema(type=openapi.TYPE_STRING, description="Sensitivity info"),
                    },
                    example={
                        "bio": "Yeni biyografi",
                        "age": 25,
                        "age_category": "4",
                        "sensitivity": "Polen"
                    }
                )
            },
            required=[]
        ),
        responses={
            200: openapi.Response(
                description="Profile updated successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'username': openapi.Schema(type=openapi.TYPE_STRING),
                        'first_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'last_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                        'bio': openapi.Schema(type=openapi.TYPE_STRING),
                        'age': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'age_category': openapi.Schema(type=openapi.TYPE_STRING),
                        'sensitivity': openapi.Schema(type=openapi.TYPE_STRING),
                    },
                    example={
                        "username": "aysenur",
                        "first_name": "Ayşe",
                        "last_name": "Nur",
                        "email": "aysenur@example.com",
                        "bio": "Yeni biyografi",
                        "age": 25,
                        "age_category": "4",
                        "sensitivity": "Polen"
                    }
                )
            ),
            400: openapi.Response(
                description="Invalid input",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "user_errors": openapi.Schema(type=openapi.TYPE_OBJECT, description="Errors from user serializer"),
                        "profile_errors": openapi.Schema(type=openapi.TYPE_OBJECT, description="Errors from profile serializer"),
                    },
                    example={
                        "user_errors": {"email": ["This field must be unique."]},
                        "profile_errors": {}
                    }
                )
            ),
            401: openapi.Response(
                description="Authentication required",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "detail": openapi.Schema(type=openapi.TYPE_STRING)
                    },
                    example={"detail": "Authentication credentials were not provided."}
                )
            )
        }
    )

    def put(self, request):
        token = request.COOKIES.get("jwt")
        payload = isTokenValid(token=token)
        user = getUserByID(payload)

        data = request.data
        profile_data = data.pop('profile', {})
        profile_data['user'] = user.id

        user_serializer = UserSerializer(user, data=data, partial=True)
        profile_serializer = ProfileSerializer(user.profile, data=profile_data, partial=True)

        if user_serializer.is_valid() and profile_serializer.is_valid():
            user_serializer.save()
            profile_serializer.save()
            result = user_serializer.data | profile_serializer.data
            return Response(result, status=status.HTTP_200_OK)
        
        errors = {
            "user_errors": user_serializer.errors,
            "profile_errors": profile_serializer.errors
        }
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)


