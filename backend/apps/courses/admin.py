"""
Django Admin configuration for Courses app.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Category, Course, Module


class ModuleInline(admin.TabularInline):
    """Inline editor for a course's modules."""

    model = Module
    extra = 0
    fields = ("order", "title", "description")
    ordering = ("order",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin configuration for the Category model."""

    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}  # Auto-generate slug from name
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "is_active")}),
        (
            _("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin configuration for the Course model."""

    list_display = (
        "title",
        "instructor",
        "category",
        "difficulty",
        "price",
        "is_published",
        "created_at",
    )
    list_filter = ("is_published", "difficulty", "category", "created_at")
    search_fields = (
        "title",
        "description",
        "instructor__email",
        "instructor__username",
    )
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("is_published",)  # Edit directly in list view
    inlines = [ModuleInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("title", "slug", "description", "instructor", "category")},
        ),
        (_("Media"), {"fields": ("thumbnail",)}),
        (
            _("Course Details"),
            {
                "fields": (
                    "price",
                    "difficulty",
                    "duration_hours",
                    "what_you_will_learn",
                    "requirements",
                )
            },
        ),
        (_("Publishing"), {"fields": ("is_published",)}),
        (
            _("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        """
        Optimize queries with select_related.

        This reduces database queries by fetching related objects
        (instructor, category) in a single query using SQL JOIN.
        """
        qs = super().get_queryset(request)
        return qs.select_related("instructor", "category")


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    """Admin configuration for the Module model."""

    list_display = ("title", "course", "order", "created_at")
    list_filter = ("course",)
    search_fields = ("title", "description", "course__title")
    list_editable = ("order",)
    ordering = ("course", "order")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("course", "order", "title", "description")}),
        (
            _("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("course")
