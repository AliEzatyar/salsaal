from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib import messages
from accounts.models import User, CUSTOMER, SHOP
from .forms import UserRegForm, VendorRegForm
from django.db.transaction import atomic

# Create your views here.
def register_vendor(request):
    # POST
    if request.method == "POST":
        u_form = UserRegForm(request.POST)
        v_form = VendorRegForm(request.POST,files=request.FILES)
        # both forms are valid
        if u_form.is_valid() and v_form.is_valid():
            cd = u_form.cleaned_data
            user = u_form.save(commit=False)
            user.set_password(cd['password'])
            user.role = SHOP  
            with atomic():
                user.save()
                # registering the shop
                vendor = v_form.save(commit=False)
                vendor.user = user
                vendor.user_profile = user.profile
                vendor.save()
                messages.success(
                    request, message="Your details were saved and we are verifiying your documents, answer will be sent through the email you provided us."
                )
                # job done
                return redirect(reverse("accounts:reg_vend"))
            
        # forms have got errors
        else:
            messages.error(
                request, message="Please fix the errors and resubmit the form."
            )
            return render(
                request,
                "vendor/register-vendor.html",
                {"u_form": u_form, "v_form": v_form},
            )

    # GET
    u_form = UserRegForm()
    v_form = VendorRegForm()
    return render(
        request, "vendor/register-vendor.html", {"u_form": u_form, "v_form": v_form}
    )


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
            messages.success(
                request, message="Your account has been created successfully!"
            )
            return redirect(reverse("accounts:reg_user"))

        # form has got errors
        else:
            messages.error(
                request, message="Please fix the errors and resubmit the form."
            )
            return render(
                request,
                "accounts/register_user.html",
                {"form": form},
            )

    # GET
    reg_form = UserRegForm()
    return render(request, "accounts/register_user.html", {"form": reg_form})
