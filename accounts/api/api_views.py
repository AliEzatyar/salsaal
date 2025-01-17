from rest_framework import generics
from .serializers import UserCreationSerializer,UserDetailSerializer
from ..models import User
from rest_framework import permissions

class RegisterUser(generics.CreateAPIView):
    serializer_class = UserCreationSerializer
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]



class UpdateDeleteRetriveUser(generics.RetrieveUpdateDestroyAPIView):
    """
        it works with 4 methods:
        GET --> retrieve user data
        PUT --> update user
        DELETE> delete the user account itself
        NOTE: this view uses default authentication class which need JWT-token
        for every request
    """
    serializer_class =  UserDetailSerializer
    queryset = User.objects.all()
    
    def get_object(self):
        """this ensures that only the user itself works on its account"""
        return self.request.user