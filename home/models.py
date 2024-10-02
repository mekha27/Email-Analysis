from django.db import models
from django.contrib.auth.models import User

# models.py

from django.db import models
from django.contrib.auth.models import User

class Email(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emails')
    content = models.TextField()
    received_at = models.DateTimeField(auto_now_add=True)
    is_received = models.BooleanField(default=True)  # New field to indicate if the email is received

    def __str__(self):
        return f"Email from {self.user} at {self.received_at}"


class SentimentAnalysisResult(models.Model):
    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name='sentiment_results')  # Add related_name
    sentiment_label = models.CharField(max_length=20)  # Sentiment (e.g., Positive, Negative, Neutral)
    sentiment_score = models.FloatField()  # Polarity score from TextBlob
    analyzed_at = models.DateTimeField(auto_now_add=True)  # When the analysis was done

    def __str__(self):
        return f"Analysis for {self.email} - Sentiment: {self.sentiment_label}"


