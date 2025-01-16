from rest_framework import generics
from .serializers import UserCreationSerializer,UserDetailSerializer
from ..models import User
from rest_framework import permissions

class RegisterUser(generics.CreateAPIView):
    serializer_class = UserCreationSerializer
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]



class UpdateDeleteRetriveUser(generics.RetrieveUpdateDestroyAPIView):
    serializer_class =  UserDetailSerializer
    queryset = User.objects.all()
    
    def get_object(self):
        return self.request.user