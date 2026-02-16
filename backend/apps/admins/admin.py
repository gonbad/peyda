from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import AdminProfile, AdminPermission, AdminActivityLog


class AdminProfileInline(admin.StackedInline):
    model = AdminProfile
    can_delete = False
    verbose_name_plural = 'پروفایل ادمین'


class AdminPermissionInline(admin.TabularInline):
    model = AdminPermission
    extra = 1
    verbose_name_plural = 'دسترسی‌ها'


class UserAdmin(BaseUserAdmin):
    inlines = [AdminProfileInline, AdminPermissionInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active']
    list_filter = ['is_staff', 'is_superuser', 'is_active']


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(AdminActivityLog)
class AdminActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'object_id', 'created_at']
    list_filter = ['action', 'model_name', 'created_at']
    search_fields = ['user__username', 'model_name']
    readonly_fields = ['user', 'action', 'model_name', 'object_id', 'details', 'created_at']
    date_hierarchy = 'created_at'
