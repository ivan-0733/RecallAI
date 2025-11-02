from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from apps.application_user.models import User
from apps.pdi_texts.models import (
    PDIText, 
    InitialQuiz, 
    QuizAttempt, 
    UserProfile,
    MaterialEffectiveness,
    MaterialRequest,
    UserDidacticMaterial
)


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
            user = authenticate(
                request=self.context.get('request'),
                username=email,
                password=password
            )
            
            if not user:
                raise serializers.ValidationError({
                    "detail": "Email o contraseña incorrectos."
                })
            
            if not user.is_active:
                raise serializers.ValidationError({
                    "detail": "Esta cuenta está desactivada."
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


class PDITextListSerializer(serializers.ModelSerializer):
    """Serializer para listar textos (sin contenido completo)"""
    
    word_count = serializers.SerializerMethodField()
    has_been_attempted = serializers.SerializerMethodField()
    
    class Meta:
        model = PDIText
        fields = [
            'id',
            'title',
            'description',
            'topic',
            'difficulty',
            'estimated_time_minutes',
            'word_count',
            'has_quiz',
            'has_been_attempted',
            'order'
        ]
    
    def get_word_count(self, obj):
        return obj.word_count()
    
    def get_has_been_attempted(self, obj):
        """Verifica si el usuario ya intentó este texto"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return QuizAttempt.objects.filter(
                user=request.user,
                quiz__text=obj
            ).exists()
        return False


class PDITextDetailSerializer(serializers.ModelSerializer):
    """Serializer para detalle de texto (incluye contenido completo)"""
    
    word_count = serializers.SerializerMethodField()
    has_quiz = serializers.BooleanField(read_only=True)
    previous_attempts = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_type = serializers.SerializerMethodField()
    has_file = serializers.SerializerMethodField()
    
    class Meta:
        model = PDIText
        fields = [
            'id',
            'title',
            'description',
            'content',
            'topic',
            'difficulty',
            'estimated_time_minutes',
            'word_count',
            'has_quiz',
            'previous_attempts',
            'file_url',
            'file_type',
            'has_file'
        ]
    
    def get_word_count(self, obj):
        return obj.word_count()
    
    def get_previous_attempts(self, obj):
        """Obtiene intentos previos del usuario en este texto"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            attempts = QuizAttempt.objects.filter(
                user=request.user,
                quiz__text=obj
            ).values('attempt_number', 'score', 'created_at')
            return list(attempts)
        return []
    
    def get_file_url(self, obj):
        """Obtiene URL del archivo original si existe"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None
    
    def get_file_type(self, obj):
        """Obtiene tipo de archivo (pdf, txt)"""
        if obj.file:
            extension = obj.file.name.split('.')[-1].lower()
            return extension
        return None
    
    def get_has_file(self, obj):
        """Verifica si tiene archivo original"""
        return bool(obj.file)


class InitialQuizSerializer(serializers.ModelSerializer):
    """Serializer para cuestionario inicial"""
    
    text_title = serializers.CharField(source='text.title', read_only=True)
    
    class Meta:
        model = InitialQuiz
        fields = [
            'id',
            'text',
            'text_title',
            'questions_json',
            'total_questions'
        ]


class QuizSubmissionSerializer(serializers.Serializer):
    """Serializer para recibir respuestas del cuestionario"""
    
    quiz_id = serializers.IntegerField()
    answers = serializers.ListField(
        child=serializers.DictField(),
        help_text="Array de {question_index: 0-19, selected_answer: 'A'}"
    )
    time_spent_seconds = serializers.IntegerField()


class QuizAttemptSerializer(serializers.ModelSerializer):
    """Serializer para mostrar resultado de intento"""
    
    text_title = serializers.CharField(source='quiz.text.title', read_only=True)
    passed = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id',
            'text_title',
            'attempt_number',
            'score',
            'weak_topics',
            'time_spent_seconds',
            'passed',
            'created_at'
        ]
    
    def get_passed(self, obj):
        return obj.passed()


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer para perfil de usuario"""
    
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'email',
            'full_name',
            'weak_topics',
            'study_streak',
            'last_study_date',
            'total_study_time_minutes'
        ]
    
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"


class MaterialRecommendationSerializer(serializers.Serializer):
    """Serializer para la respuesta de recomendación"""
    has_recommendation = serializers.BooleanField()
    recommended_type = serializers.CharField(allow_null=True)
    expected_improvement = serializers.FloatField()
    all_effectiveness = serializers.DictField()
    reason = serializers.CharField()
    message = serializers.CharField()


class MaterialGenerateRequestSerializer(serializers.Serializer):
    """Serializer para solicitud de generación de material"""
    material_type = serializers.ChoiceField(choices=[
        'flashcard',
        'decision_tree',
        'mind_map',
        'summary'
    ])
    attempt_id = serializers.IntegerField()
    was_recommended = serializers.BooleanField(default=False)
    followed_recommendation = serializers.BooleanField(required=False, allow_null=True)


class UserDidacticMaterialSerializer(serializers.ModelSerializer):
    """Serializer para material didáctico generado"""
    text_title = serializers.CharField(source='text.title', read_only=True)
    material_type_display = serializers.CharField(source='get_material_type_display', read_only=True)
    
    class Meta:
        model = UserDidacticMaterial
        fields = [
            'id',
            'text_title',
            'material_type',
            'material_type_display',
            'html_content',
            'weak_topics',
            'requested_at',
            'generated_at',
            'generation_time_seconds'
        ]