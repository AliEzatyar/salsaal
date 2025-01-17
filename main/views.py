from django.shortcuts import render
from django.contrib import messages
# Create your views here.

def home(request):
    messages.success(request,"you are at home!")
    return render(request,"base/home.html")