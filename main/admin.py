from django.contrib import admin
from .models import User, DriverProfile, Vehicle, Trip, Booking, ChatThread, ChatMessage, UserReport, FCMDevice
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.utils.html import format_html
import os
from django.urls import reverse
from firebase_admin import messaging
from django.contrib.admin.models import LogEntry



def send_push_notification(token, title, body, data=None):
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        data=data or {}

    )
    response = messaging.send(message)


admin.site.register([Trip,
                    Booking, ChatThread, ChatMessage, FCMDevice])


def get_file_preview(file_field, title):
    """Generic method to handle different file types"""
    if not file_field:
        return f"No {title} uploaded"

    try:
        file_url = file_field.url
        file_name = os.path.basename(file_field.name)
        file_ext = os.path.splitext(file_name)[1].lower()

        # Image files
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            return format_html(
                '<div>'
                '<img src="{}" style="max-width: 300px; max-height: 300px; object-fit: contain; border: 1px solid #ddd; border-radius: 4px;" />'
                '<br><a href="{}" target="_blank">Download {}</a>'
                '</div>',
                file_url, file_url, file_name
            )

        # PDF files
        elif file_ext == '.pdf':
            pdf_url = reverse('pdf_viewer', args=[file_field.name])
            return format_html(
                '<div>'
                '<iframe src="{}" width="400" height="300" style="border: 1px solid #ddd;"></iframe>'
                '<br><a href="{}" target="_blank">📄 Download PDF: {}</a>'
                '</div>',
                pdf_url, file_url, file_name
            )

        # Document files (Word, etc.)
        elif file_ext in ['.doc', '.docx', '.txt', '.rtf']:
            return format_html(
                '<div>'
                '<div style="padding: 20px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9; text-align: center;">'
                '<span style="font-size: 48px;">📄</span>'
                '<br><strong>Document File</strong>'
                '<br>{}'
                '</div>'
                '<br><a href="{}" target="_blank">📄 Download Document: {}</a>'
                '</div>',
                file_name, file_url, file_name
            )

        # Other file types
        else:
            return format_html(
                '<div>'
                '<div style="padding: 20px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9; text-align: center;">'
                '<span style="font-size: 48px;">📎</span>'
                '<br><strong>File</strong>'
                '<br>{}'
                '</div>'
                '<br><a href="{}" target="_blank">📎 Download: {}</a>'
                '</div>',
                file_name, file_url, file_name
            )

    except ValueError:
        return f"{title} file not found"


class CustomUserAdmin(admin.ModelAdmin):
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        
        # Only show permissions to superusers
        if not request.user.is_superuser:
            # Create a new fieldsets tuple without permissions
            new_fieldsets = []
            for name, options in fieldsets:
                if name == 'Permissions':
                    # Skip the entire Permissions section
                    continue
                elif name is None and 'fields' in options:
                    # This is usually the first fieldset, check if it contains permission fields
                    fields = options['fields']
                    filtered_fields = [
                        field for field in fields 
                        if field not in ['user_permissions', 'groups', 'is_superuser']
                    ]
                    if filtered_fields:  # Only include if there are remaining fields
                        new_fieldsets.append((name, {**options, 'fields': filtered_fields}))
                else:
                    new_fieldsets.append((name, options))
            
            fieldsets = tuple(new_fieldsets)
        
        return fieldsets
    
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        
        # Make permissions read-only for non-superusers (as backup)
        if not request.user.is_superuser:
            readonly_fields.extend(['user_permissions', 'groups', 'is_superuser'])
        
        return readonly_fields

    def has_change_permission(self, request, obj=None):
        # Allow staff to change users, but permissions will be hidden/readonly
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

admin.site.register(User, CustomUserAdmin)

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    change_form_template = "admin/main/vehicle/change_form.html"
    readonly_fields = ['registration_preview', 'insurance_preview']

    def response_change(self, request, obj):
        if "_mark_verified" in request.POST:
            obj.verified = True
            obj.save()

            # Send notification to the driver
            driver = obj.driver.user

            data = {
                "vehicle_id": str(obj.id),
                "screen": "vehicle-details",
            }

            fcm_tokens = FCMDevice.objects.filter(
                user=driver).values_list('token', flat=True)
            for token in fcm_tokens:
                send_push_notification(
                    token, "Vehicle Verified", f"You vehicle [{str(obj)}] has been verified.", data)

            self.message_user(
                request, "Vehicle marked as verified.", messages.SUCCESS)
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    def registration_preview(self, obj):
        return get_file_preview(obj.vehicle_registration_upload, "Registration")
    registration_preview.short_description = 'Registration Preview'

    def insurance_preview(self, obj):
        return self.get_file_preview(obj.insurance_upload, "Insurance")
    insurance_preview.short_description = 'Insurance Preview'


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    change_form_template = "admin/main/driverprofile/change_form.html"
    readonly_fields = ['license_preview', 'national_id_preview']

    def response_change(self, request, obj):
        if "_mark_verified" in request.POST:
            obj.verification_status = 'verified'
            obj.save()

            # Send notification to the driver
            driver = obj.user

            data = {
                "screen": "my-account",
            }

            fcm_tokens = FCMDevice.objects.filter(
                user=driver).values_list('token', flat=True)
            for token in fcm_tokens:
                send_push_notification(
                    token, "Account Verified", f"Your driver profile has been verified.", data)

            self.message_user(
                request, "Driver profile marked as verified.", messages.SUCCESS)
            return HttpResponseRedirect(".")
        if "_mark_rejected" in request.POST:
            obj.verification_status = 'rejected'
            obj.save()

            # Send notification to the driver
            driver = obj.user

            data = {
                "screen": "my-account",
            }

            fcm_tokens = FCMDevice.objects.filter(
                user=driver).values_list('token', flat=True)
            for token in fcm_tokens:
                send_push_notification(
                    token, "Account Rejected", f"You driver profile has been rejected.", data)

            self.message_user(
                request, "Driver profile marked as rejected.", messages.WARNING)
            return HttpResponseRedirect(".")
        if "_go_to_next" in request.POST:
            next_obj = (
                DriverProfile.objects
                .filter(verification_status='pending')
                .exclude(pk=obj.pk)
                .order_by('pk')  # adjust ordering as you need
                .first()
            )
            if next_obj:
                url = reverse(
                    'admin:main_driverprofile_change', args=[next_obj.pk]
                )
                return HttpResponseRedirect(url)
            else:
                self.message_user(
                    request, "No more pending driver profiles.", messages.INFO)
                return HttpResponseRedirect(".")

        return super().response_change(request, obj)

    def license_preview(self, obj):
        return get_file_preview(obj.license_upload, "License")
    license_preview.short_description = 'License Preview'

    def national_id_preview(self, obj):
        return get_file_preview(obj.national_id_upload, "National ID")
    national_id_preview.short_description = 'National ID Preview'


@admin.register(UserReport)
class UserReportAdmin(admin.ModelAdmin):
    change_form_template = "admin/main/userreport/change_form.html"

    def response_change(self, request, obj):
        if "_block_user" in request.POST:
            user = obj.reported_user
            user.is_active = False
            user.save()
            obj.is_resolved = True
            
            # Send notification to the driver
            fcm_tokens = FCMDevice.objects.filter(
                user=user).values_list('token', flat=True)
            for token in fcm_tokens:
                send_push_notification(
                    token, "Account Blocked", f"After a review, your account has been blocked, we have sent you an email for further clarity.")

            self.message_user(
                request, f"User '{user.username}' has been blocked.", messages.WARNING
            )
            return HttpResponseRedirect(".")
        
        if "_unblock_user" in request.POST:
            user = obj.reported_user
            user.is_active = True
            user.save()
            obj.is_resolved = True
            
            # Send notification to the driver
            fcm_tokens = FCMDevice.objects.filter(
                user=user).values_list('token', flat=True)
            for token in fcm_tokens:
                send_push_notification(
                    token, "Account UbBlocked", f"After a review, your account has been unblocked, we have sent you an email for further clarity.")

            self.message_user(
                request, f"User '{user.username}' has been blocked.", messages.WARNING
            )
            return HttpResponseRedirect(".")

        if "_go_to_next" in request.POST:
            next_obj = (
                UserReport.objects
                .filter(is_resolved=False)
                .exclude(pk=obj.pk)
                .order_by('pk')  # adjust ordering as you need
                .first()
            )
            if next_obj:
                url = reverse(
                    'admin:main_userreport_change', args=[next_obj.pk]
                )
                return HttpResponseRedirect(url)
            else:
                self.message_user(
                    request, "No more unresolved user reports.", messages.INFO)
                return HttpResponseRedirect(".")
            
        return super().response_change(request, obj)


class LogEntryAdmin(admin.ModelAdmin):
    readonly_fields = [f.name for f in LogEntry._meta.fields]
    list_display = ['action_time', 'user', 'content_type', 'object_repr', 'action_flag', 'change_message']
    list_filter = ['user', 'content_type', 'action_flag']
    search_fields = ['object_repr', 'change_message']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

admin.site.register(LogEntry, LogEntryAdmin)