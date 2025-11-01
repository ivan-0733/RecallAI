from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from apps.application_user.models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer para registro de nuevos usuarios"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'password', 'password_confirm')
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
        }
    
    def validate(self, attrs):
        """Validar que las contraseñas coincidan"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "Las contraseñas no coinciden."
            })
        return attrs
    
    def create(self, validated_data):
        """Crear usuario nuevo"""
        validated_data.pop('password_confirm')
        
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data.get('username', validated_data['email']),
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password']
        )
        
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer para login de usuarios"""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        """Validar credenciales"""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            # Buscar usuario por email
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    "email": "No existe un usuario con este email."
                })
            
            # Autenticar con username (porque Django usa username por defecto)
            user = authenticate(username=user.username, password=password)
            
            if not user:
                raise serializers.ValidationError({
                    "password": "Contraseña incorrecta."
                })
            
            if not user.is_active:
                raise serializers.ValidationError({
                    "email": "Esta cuenta está desactivada."
                })
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError({
                "detail": "Debe proporcionar email y contraseña."
            })


class UserSerializer(serializers.ModelSerializer):
    """Serializer para información del usuario"""
    
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'is_active', 'date_joined')
        read_only_fields = ('id', 'date_joined')