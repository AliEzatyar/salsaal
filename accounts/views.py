from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib import messages
from accounts.models import User, CUSTOMER, SHOP
from .forms import UserRegForm


# Create your views here.
def register_rest(request):
    if request.method == "POST":
        pass
    reg_form = UserRegForm()
    return render(request, "accounts/register-restaurant.html", {"form": reg_form})


def register_user(request):
    if request.method == "POST":
        form = UserRegForm(request.POST)
        # form is valid
        if form.is_valid():
            cd = form.cleaned_data
            user = form.save(commit=False)
            # determining role and setting hashed password
            user.role = CUSTOMER
            user.set_password(cd["password"])
            user.save()
            # everything successfull
            messages.success(request,message='Your account has been created successfully!')
            return redirect(reverse("accounts:reg_user"))

        # form has got errors
        else:
            messages.error(request,message="Please fix the errors and resubmit the form.")
            return render(
                request,
                "accounts/register_user.html",
                {"form": form},
            )

    # GET
    reg_form = UserRegForm()
    return render(request, "accounts/register_user.html", {"form": reg_form})
