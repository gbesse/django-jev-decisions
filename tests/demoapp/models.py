"""Purpose: Supply a small host model whose changing text exercises stale decision protection."""
from django.db import models
class Ticket(models.Model):
    text = models.TextField()
def ticket_state(ticket):
    return {"text": ticket.text}
