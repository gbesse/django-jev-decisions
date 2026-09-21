"""Purpose: Add explicit model evaluation actions and a read-only decision review history to Django admin."""
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from .models import DecisionJob
from .services import enqueue

class JevDecisionAdminMixin:
    jev_rule = None
    @admin.action(description="Queue Jev evaluation", permissions=["change"])
    def evaluate_with_jev(self, request, queryset):
        if not request.user.has_perm("jev_decisions.add_decisionjob"):
            raise PermissionDenied("Decision creation permission required")
        count = 0
        for instance in queryset:
            if not self.has_change_permission(request, instance): raise PermissionDenied
            enqueue(instance, self.jev_rule); count += 1
        self.message_user(request, f"Queued {count} decisions.", messages.SUCCESS)
    def get_actions(self, request):
        actions = super().get_actions(request)
        if self.jev_rule and self.has_change_permission(request) and request.user.has_perm("jev_decisions.add_decisionjob"):
            actions["evaluate_with_jev"] = (type(self).evaluate_with_jev, "evaluate_with_jev", "Queue Jev evaluation")
        return actions

@admin.register(DecisionJob)
class DecisionJobAdmin(admin.ModelAdmin):
    list_display = ("rule_name", "model_label", "object_pk", "status", "outcome", "created_at")
    list_filter = ("status", "rule_name", "outcome")
    search_fields = ("object_pk", "rule_name")
    readonly_fields = tuple(field.name for field in DecisionJob._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
