from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages

from .forms import BusinessSignUpForm


def register_view(request):
    if request.method == "POST":
        form = BusinessSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created and you are now logged in.")
            return redirect("services:home")  # change to your dashboard url name
    else:
        form = BusinessSignUpForm()

    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "You are now logged in.")
            return redirect("services:home")
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
    return render(request, "accounts/logged_out.html")
