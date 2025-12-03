from django.shortcuts import render


def home(request):
    return render(request, "services/home.html")