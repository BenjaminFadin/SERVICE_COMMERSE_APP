from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages

from .forms import UserSignUpForm 

# Need add profile settings page, password reset using email also

def login_view(request):
    if request.method == "POST":
        # We pass request data to the form
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "You are now logged in.")
            return redirect("services:home") # Ensure this URL pattern exists
        else:
            # If invalid, we fall through to render the template with form errors
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm(request)

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    # If you want logout only via POST (more secure):
    # if request.method == "POST":
    #     logout(request)
    # else:
    #     return redirect("home")

    logout(request)  # logs out current user
    return redirect('services:home')

def auth_view(request):
    # Initialize forms
    login_form = AuthenticationForm()
    register_form = UserSignUpForm() # CHANGED: Use User form
    
    active_section = 'login'

    if request.method == "POST":
        # --- LOGIN LOGIC ---
        if 'login_submit' in request.POST:
            active_section = 'login'
            login_form = AuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)
                # messages.success(request, "You are now logged in.")
                return redirect("services:home")
            else:
                messages.error(request, "Invalid username or password.")

        # --- REGISTER LOGIC (User) ---
        elif 'register_submit' in request.POST:
            active_section = 'register'
            # CHANGED: Use UserSignUpForm
            register_form = UserSignUpForm(request.POST) 
            if register_form.is_valid():
                user = register_form.save()
                login(request, user)
                # messages.success(request, "Account created! Welcome.")
                return redirect("services:home")
            else:
                messages.error(request, "Registration failed. Please fix the errors.")

    context = {
        "login_form": login_form,
        "register_form": register_form,
        "active_section": active_section, 
    }
    return render(request, "accounts/auth_combined.html", context)
