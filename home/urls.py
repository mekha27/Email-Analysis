from django.urls import path
from .views import *
from django.views.generic import TemplateView

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html'), name='index'),  # Home page
    path('logout/', logout, name='logout'),  # Logout
    path('home/', emails_list, name='home'),  # List emails
    path('all-emails/', emails_list, name='all_emails'),  # Route for all emails
    path('seen-emails/', read_emails_list, name='seen_emails'),  # Route for seen/read emails
    path('send-email/', send_email, name='send_email'),
    path('download-report/', download_report, name='download_report'),
    path('chatbot/', chatbot, name='chatbot'),
    path('analyze_sentiment/', analyze_sentiment, name='analyze_sentiment'),  # Route for sentiment analysis
]