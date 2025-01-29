from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from accounts.models import User, CUSTOMER, SHOP
from .forms import UserRegForm, VendorRegForm
from django.db.transaction import atomic
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator

from .utils import send_email
from .utils import send_forgot_email



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
                # sending the email
                # registering the shop
                vendor = v_form.save(commit=False)
                vendor.user = user
                vendor.user_profile = user.profile
                vendor.save()
                send_email(request, user)
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
            send_email(request, user)

            # everything successfull
            messages.success(
                request, message="Your account has been created successfully!"
            )
            return redirect(reverse("main:home"))

        # form has got errors
        else:
            messages.error(
                request, message="Please fix the errors and resubmit the form."
            )
            return render(
                request,
                "customer/register_user.html",
                {"form": form},
            )

    # GET
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    reg_form = UserRegForm()
    return render(request, "customer/register_user.html", {"form": reg_form})


# email verification
def activate_user_account(request, uidb64: bytes, token):
    try:
        user_id = urlsafe_base64_decode(uidb64)
        user = User.objects.filter(pk=user_id).first()
    except (TypeError, ValueError, OverflowError):
        user = None
    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Email Verification Successfull!")
        auth.login(request, user)
        return redirect("accounts:dashboard")
    messages.error(request, "Token Invalid!")

    return render(request, "accounts/verification_invalid.html")


# 1
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email", None)
        if email:
            user = User.objects.filter(email=email).first()
            if user:
                send_forgot_email(request, user)
                return render(request, "accounts/password_reset_verification_sent.html")
        return render(request, "accounts/forgot_password.html", {"no_email": True})
    return render(request, "accounts/forgot_password.html")


# 2
def reset_password_validate(request, uidb64, token):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.filter(pk=user_id).first()
    except (TypeError, ValueError, OverflowError):
        user = None
    if user and default_token_generator.check_token(user, token):
        request.session["uid"] = user_id
        return redirect("accounts:reset_password")

    messages.error(request, "Token Invalid!")
    return render(request, "accounts/verification_invalid.html")


# 3
def reset_password(request):
    error = False  # two errors possible
    if request.method == "POST":
        # getting the user by its id saved in session
        user = User.objects.filter(pk=request.session.get("uid", None)).first()
        new_password = request.POST["password"]
        new_password_confirm = request.POST["password_confirm"]
        # if user found, set the new password for it
        if user:
            if new_password == new_password_confirm:
                user.set_password(new_password)
                user.save()
                request.session["uid"] = None
                return redirect("accounts:login")
            error = "Passwords didn't match!"
        else:
            error = "Password Reset Not Allowed"
    return render(request, "accounts/reset_password.html", {"error": error})


def login(request):
    # POST
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = auth.authenticate(email=email, password=password)
        if user:
            auth.login(request, user)
            messages.info(request, "خوش آمدید")
            if request.POST.get("next") != "None":
                return redirect(request.build_absolute_uri(request.POST.get("next")))

            # redirecting to the dashboard
            return redirect("accounts:dashboard")

        # authentication invalid
        return render(
            request, "accounts/account.html", {"error": "Email or password incorrect"}
        )

    # GET
    elif request.user.is_authenticated:
        return redirect("accounts:dashboard")

    next_ = request.GET.get("next")
    return render(request, "accounts/account.html", {"next": next_})


@login_required
def logout(request):
    auth.logout(request)
    messages.error(request, "شما از حساب خویش خارج شدید!")
    return redirect("main:home")


@login_required
def dashboard(request):
    if request.user.is_admin:
        return redirect("/admin")
    elif request.user.get_role() == "Customer":
        return redirect("accounts:customer_dashboard")
    elif request.user.get_role() == "Shop":
        return redirect("vendor:vendor_dashboard")




@login_required
@user_passes_test(customer_tester)
def customer_dashboard(request):
    return render(request, "customer/dashboard.html")
