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
        
        # Get the file (might be None if they didn't upload one)
        profile_pic = request.FILES.get('profile_pic') 
        
        # Pass it to db_utils
        success, message = create_user(email, password, channel_name, profile_pic)
        
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
            # CREATE SESSION
            request.session['user_email'] = email
            request.session['channel_name'] = user['channel_name']
            
            # Store avatar_key in session so we can use it later (e.g. during video upload)
            # Use .get() in case old users don't have this field
            request.session['avatar_key'] = user.get('avatar_key') 
            
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid email or password")
            
    return render(request, 'login.html')

def logout_view(request):
    request.session.flush() # Clears cookies
    return redirect('login')