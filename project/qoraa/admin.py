from django.contrib import admin
from django import forms
from .models import PlatformQoraaVendor, Food


class PlatformQoraaVendorForm(forms.ModelForm):
    class Meta:
        model = PlatformQoraaVendor
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        vendor = kwargs.pop("vendor", None)
        super().__init__(*args, **kwargs)

        if vendor:
            self.fields["food_items"].queryset = Food.objects.filter(vendor=vendor)
        else:
            # new object, no vendor yet -> empty queryset
            self.fields["food_items"].queryset = Food.objects.none()


from .models import PlatformQoraaVendor, Qoraa

@admin.register(Qoraa)
class QoraaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "vendor",
        "start",
        "end",
        "status",
        "winner",
        "is_platform",
        "joiners_limit",
        "is_claimed",
        "created_at",
    )
    list_filter = ("status", "is_platform", "is_claimed", "start", "end")
    search_fields = ("title", "vendor__vendor_name", "winner__name")
    ordering = ("-start",)
    readonly_fields = ["created_at"]


@admin.register(PlatformQoraaVendor)
class PlatformQoraaVendorAdmin(admin.ModelAdmin):
    form = PlatformQoraaVendorForm
    list_display = ("id", "vendor", "is_active")
    list_editable = ["is_active"]
    list_filter = ("is_active",)
    search_fields = ("vendor__vendor_name", "vendor__id")
    ordering = ("-id",)

    def get_form(self, request, obj=None, **kwargs):
        Form = super().get_form(request, obj, **kwargs)

        class WrappedForm(Form):
            def __init__(self2, *args, **kw):
                kw["vendor"] = obj.vendor if obj else None
                super().__init__(*args, **kw)

        return WrappedForm
