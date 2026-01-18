from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from django.shortcuts import get_object_or_404
from .models import Promotion, Vendor
from admins.admin import revenue_admin_site
from django.utils.html import format_html
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import re


def generate_vendor_qrcode(vendor_id, vendor_name):
    """Generate a QR code image with vendor name for the given vendor."""
    url = f"https://zayton.llc/restaurants/{vendor_id}"
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    # Create a new image with space for the vendor name
    qr_width, qr_height = qr_img.size
    padding = 40
    text_area_height = 60
    
    final_img = Image.new('RGB', (qr_width, qr_height + text_area_height), 'white')
    final_img.paste(qr_img, (0, 0))
    
    # Add vendor name text
    draw = ImageDraw.Draw(final_img)
    
    # Try to use a nice font, fallback to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 24)
        except (IOError, OSError):
            font = ImageFont.load_default()
    
    # Get text bounding box for centering
    text_bbox = draw.textbbox((0, 0), vendor_name, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = (qr_width - text_width) // 2
    text_y = qr_height + (text_area_height - (text_bbox[3] - text_bbox[1])) // 2
    
    draw.text((text_x, text_y), vendor_name, font=font, fill="black")
    
    return final_img


def sanitize_filename(name):
    """Sanitize vendor name for use as filename."""
    # Replace spaces and special characters
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name


# Register your models here.
class VendAdmin(admin.ModelAdmin):
    list_display = ["id", "vendor_name", "user", "vendor_type", "is_approved", "is_available", "avg_rating", "city", "location_link", "qrcode_download", "created_at"]
    list_editable = ["is_approved", "is_available"]
    list_filter = ["is_approved", "is_available", "vendor_type", "city", "created_at"]
    search_fields = ["vendor_name", "user__name", "user__phone_number", "city"]
    ordering = ("-avg_rating", "-created_at")
    readonly_fields = ["created_at", "modified_at", "avg_rating", "rating_count", "qrcode_preview"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:vendor_id>/download-qrcode/',
                self.admin_site.admin_view(self.download_qrcode_view),
                name='vendor_vendor_download_qrcode',
            ),
        ]
        return custom_urls + urls

    def download_qrcode_view(self, request, vendor_id):
        """View to download QR code for a vendor."""
        vendor = get_object_or_404(Vendor, pk=vendor_id)
        
        # Generate QR code
        qr_img = generate_vendor_qrcode(vendor.id, vendor.vendor_name)
        
        # Save to buffer
        buffer = BytesIO()
        qr_img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Create response
        filename = f"{sanitize_filename(vendor.vendor_name)}_qrcode.png"
        response = HttpResponse(buffer.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response

    def qrcode_download(self, obj):
        """Display download link in list view."""
        return format_html(
            '<a href="{}/download-qrcode/" class="button" style="padding: 5px 10px; background: #417690; color: white; text-decoration: none; border-radius: 3px;">📥 QR</a>',
            obj.pk
        )
    qrcode_download.short_description = "QR Code"
    qrcode_download.allow_tags = True

    def qrcode_preview(self, obj):
        """Display QR code preview and download button in detail view."""
        if not obj.pk:
            return "-"
        return format_html(
            '''
            <div style="text-align: center;">
                <p><strong>URL:</strong> https://zayton.llc/restaurants/{}</p>
                <a href="{}/download-qrcode/" class="button" style="padding: 10px 20px; background: #417690; color: white; text-decoration: none; border-radius: 5px; font-size: 14px;">
                    📥 Download QR Code
                </a>
            </div>
            ''',
            obj.pk,
            obj.pk
        )
    qrcode_preview.short_description = "QR Code"
    qrcode_preview.allow_tags = True

    def location_link(self, obj):
        if not obj.latitude or not obj.longitude:
            return "-"
        return format_html('<a href="https://www.google.com/maps?q={},{}" target="_blank">Map</a>',obj.latitude,obj.longitude)

    location_link.allow_tags = True
    location_link.short_description = "Location"

# Register your models here.
class PromotionAdmin(admin.ModelAdmin):
    list_display = ["id", "vendor", "city", "is_active", "cost_per_day", "start_date", "end_date", "created_at"]
    list_editable = ["is_active", "cost_per_day"]
    list_filter = ["is_active", "city", "start_date", "end_date"]
    search_fields = ["vendor__vendor_name", "city"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at", "modified_at"]


revenue_admin_site.register(Vendor, VendAdmin)
revenue_admin_site.register(Promotion,PromotionAdmin)
