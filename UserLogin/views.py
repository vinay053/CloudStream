import json
import boto3
from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib import messages
from .db_utils import create_user,verify_user

def signup_view(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        channel_name = request.POST['channel_name']
        
        success, message = create_user(email, password, channel_name)
        
        if success:
            messages.success(request, "Account created! Please login.")
            return redirect('login')
        else:
            messages.error(request, message)
            
    return render(request, 'signup.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        
        user = verify_user(email, password)
        
        if user:
            # CREATE SESSION (This logs them in)
            request.session['user_email'] = email
            request.session['channel_name'] = user['channel_name']
            return redirect('home') # We will make this page next
        else:
            messages.error(request, "Invalid email or password")
            
    return render(request, 'login.html')

def logout_view(request):
    request.session.flush() # Clears cookies
    return redirect('login')