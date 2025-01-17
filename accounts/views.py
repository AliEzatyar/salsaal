from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from accounts.models import User, CUSTOMER, SHOP
from .forms import UserRegForm, VendorRegForm
from django.db.transaction import atomic


# utility funciton
def vendor_tester(user):
    if user.role != 1:
        raise PermissionDenied
    return True


# utility funciton
def customer_tester(user):
    if user.role != 2:
        raise PermissionDenied
    return True


def register_vendor(request):
    # POST
    if request.method == "POST":
        u_form = UserRegForm(request.POST)
        v_form = VendorRegForm(request.POST, files=request.FILES)
        # both forms are valid
        if u_form.is_valid() and v_form.is_valid():
            cd = u_form.cleaned_data
            user = u_form.save(commit=False)
            user.set_password(cd["password"])
            user.role = SHOP
            with atomic():
                user.save()
                # registering the shop
                vendor = v_form.save(commit=False)
                vendor.user = user
                vendor.user_profile = user.profile
                vendor.save()
                messages.success(
                    request,
                    message="Your details were saved and we are verifiying your documents, answer will be sent through the email you provided us.",
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
    if request.user.is_authenticated:
        return redirect("accounts:user_dashboard")

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
    if request.user.is_authenticated:
        return redirect("accounts:user_dashboard")

    reg_form = UserRegForm()
    return render(request, "customer/register_user.html", {"form": reg_form})


def login(request):
    # POST
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = auth.authenticate(email=email, password=password)
        if user:
            auth.login(request, user)
            messages.success(request, "You are logged in...")
            if request.POST.get("next") != "None":
                return redirect(request.build_absolute_uri(request.POST.get("next")))

            # redirecting to the dashboard
            return redirect("accounts:dashboard")

        # authentication invalid
        return render(
            request, "accounts/login.html", {"error": "Email or password incorrect"}
        )

    # GET
    elif request.user.is_authenticated:
        return redirect("accounts:dashboard")

    next_ = request.GET.get("next")
    return render(request, "accounts/login.html", {"next": next_})


@login_required
def logout(request):
    auth.logout(request)
    messages.info(request, "You have logged out!")
    return redirect("main:home")


@login_required
def dashboard(request):
    if request.user.is_admin:
        return redirect("/admin")
    elif request.user.get_role() == "Customer":
        return redirect("accounts:customer_dashboard")
    elif request.user.get_role() == "Shop":
        return redirect("accounts:vend_dashboard")


@login_required
@user_passes_test(vendor_tester)
def vend_dashboard(request):
    return render(request, "vendor/vend_dashboard.html")


@login_required
@user_passes_test(customer_tester)
def customer_dashboard(request):
    return render(request, "customer/dashboard.html")
