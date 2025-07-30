from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class Profile(models.Model):

    AGE_RANGE = [
    ("1", "Baby-Todler"), # birth to age 3
    ("2", "Childhood"), # 3-13
    ("3", "Adolescent"), # 13-20
    ("4", "Young Adult"), # 20-34
    ("5", "Middle Adult"), # 35-50
    ("6", "Old Adults"), # 50 and above
    ]

    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile") # username, password, email, name, surname
    age             = models.IntegerField(blank=False)
    age_category    = models.CharField(max_length=15, choices=AGE_RANGE, default="3", null=False )
    bio             = models.TextField(blank=True, max_length=500)
    sensitivity     = models.TextField(blank=True, max_length=250)
    # image = models.ImageField(upload_to="profile_pics", default="default.jpg")

    def __str__(self):
        return self.user.username