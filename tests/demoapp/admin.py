"""Purpose: Register the real addon mixin in the host model's admin."""
from django.contrib import admin
from jev_decisions.admin import JevDecisionAdminMixin
from .models import Ticket
@admin.register(Ticket)
class TicketAdmin(JevDecisionAdminMixin, admin.ModelAdmin):
    jev_rule = "support"
