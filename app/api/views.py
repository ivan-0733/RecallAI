from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import logout

from api.serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer
)
from apps.application_user.models import User
# Importamos el modelo del path para que el dashboard sepa en qué sesión va
from apps.pdi_texts.models import StudentLearningPath 

class UserRegistrationView(generics.CreateAPIView):
    """
    Vista para registro de nuevos usuarios
    POST /api/auth/register/
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generar tokens JWT
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': '¡Registro exitoso! Bienvenido a RecallAI'
        }, status=status.HTTP_201_CREATED)


class UserLoginView(APIView):
    """
    Vista para login de usuarios
    POST /api/auth/login/
    """
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer
    
    def post(self, request):
        serializer = UserLoginSerializer(
            data=request.data,
            context={'request': request}  # ← Importante pasar el contexto
        )
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Generar tokens JWT
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': f'¡Bienvenido de nuevo, {user.first_name}!'
        }, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    """
    Vista para logout de usuarios
    POST /api/auth/logout/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            logout(request)
            return Response({
                'message': 'Logout exitoso'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': 'Token inválido o expirado'
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Vista para ver y actualizar perfil del usuario
    GET/PUT /api/auth/profile/
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class UserActivePathsView(APIView):
    """
    NUEVA VISTA: Devuelve el estado del flujo experimental del usuario.
    Permite al dashboard saber si debe mostrar "Sesión 0", "Sesión 1", "Post-Test", etc.
    GET /api/user/paths/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Buscar todos los procesos de aprendizaje activos o terminados del usuario
        paths = StudentLearningPath.objects.filter(user=request.user)
        
        data = []
        for path in paths:
            status_label = "En Progreso"
            if path.current_session == 0:
                status_label = "Diagnóstico (Sesión 0)"
            elif path.is_completed:
                status_label = "Listo para Post-Test"
            else:
                status_label = f"Sesión {path.current_session}"

            data.append({
                'text_id': path.text.id,
                'text_title': path.text.title,
                'current_session': path.current_session,
                'is_completed': path.is_completed,
                'status_label': status_label,
                'started_at': path.created_at
            })
            
        return Response(data, status=status.HTTP_200_OK)