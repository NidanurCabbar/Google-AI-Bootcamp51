from django.db import models
from django.contrib.auth.models import User

class ProductAnalysis(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image_url = models.URLField(blank=True, null=True)
    extracted_text = models.TextField()
    toxic_score = models.FloatField()
    toxic_ingredients = models.JSONField()
    general_review = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analysis #{self.id} by {self.user.username} on {self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else 'N/A'}"
    

