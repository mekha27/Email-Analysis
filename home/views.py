from django.shortcuts import render, redirect
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from allauth.socialaccount.models import SocialToken, SocialApp
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
import requests
from textblob import TextBlob  # Import TextBlob for sentiment analysis
from .models import Email, SentimentAnalysisResult  # Import your models

def get_gmail_service(credentials):
    """Build and return a Gmail service object."""
    return build('gmail', 'v1', credentials=credentials)

@login_required
def emails_list(request):
    """Fetch and display the user's Gmail messages."""
    user = request.user
    emails = []
    sentiment_counts = {
        'positive': 0,
        'negative': 0,
        'neutral': 0
    }

    try:
        # Fetch the user's Google account and token
        social_account = user.socialaccount_set.get(provider='google')
        social_token = SocialToken.objects.get(account=social_account)
        social_app = SocialApp.objects.get(provider='google')

        # Set up credentials
        credentials = Credentials(
            token=social_token.token,
            refresh_token=social_token.token_secret,
            client_id=social_app.client_id,
            client_secret=social_app.secret,
            token_uri='https://oauth2.googleapis.com/token'
        )

        # Refresh credentials if expired
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        # Build the Gmail service
        service = get_gmail_service(credentials)

        # Fetch the user's Gmail messages
        results = service.users().messages().list(userId='me', maxResults=10).execute()
        messages = results.get('messages', [])

        # Fetch each message's details and save to the Email model
        for message in messages:
            email_data = service.users().messages().get(userId='me', id=message['id']).execute()
            email_snippet = email_data['snippet']
            # Save email to the database
            email_instance = Email.objects.create(user=user, content=email_snippet)
            emails.append(email_instance)  # Store the Email instance

            # Perform sentiment analysis
            blob = TextBlob(email_snippet)
            sentiment = blob.sentiment.polarity  # Get sentiment polarity (range from -1 to 1)

            # Determine sentiment label based on polarity score
            if sentiment > 0:
                sentiment_label = 'Positive'
                sentiment_counts['positive'] += 1
            elif sentiment < 0:
                sentiment_label = 'Negative'
                sentiment_counts['negative'] += 1
            else:
                sentiment_label = 'Neutral'
                sentiment_counts['neutral'] += 1

            # Save the sentiment analysis result to the database
            SentimentAnalysisResult.objects.create(
                email=email_instance,
                sentiment_label=sentiment_label,
                sentiment_score=sentiment
            )

    except SocialToken.DoesNotExist:
        return redirect('/accounts/google/login/')  # Redirect to login if no token is found
    except Exception as e:
        print(f"An error occurred: {e}")
        return HttpResponse(f"An error occurred: {str(e)}", status=500)

    # Pass the emails and sentiment counts to the template
    context = {
        'emails': emails,
        'sentiment_counts': sentiment_counts
    }
    return render(request, 'home.html', context)

def login(request):
    """Render the login page."""
    return render(request, 'login.html')

def logout(request):
    """Log out the user and redirect to home."""
    auth_logout(request)
    return redirect('/')

@login_required
def read_emails_list(request):
    """Fetch and display the user's received and sent emails."""
    user = request.user
    
    # Initialize empty lists for emails
    received_emails = list(Email.objects.filter(user=user, is_received=True))  # Convert QuerySet to list
    sent_emails = list(Email.objects.filter(user=user, is_received=False))  # Convert QuerySet to list

    sentiment_counts = {
        'positive': 0,
        'negative': 0,
        'neutral': 0
    }

    try:
        social_account = user.socialaccount_set.get(provider='google')
        social_app = SocialApp.objects.get(provider='google')
        social_token = SocialToken.objects.get(account=social_account)

        credentials = Credentials(
            token=social_token.token,
            refresh_token=social_token.token_secret,
            client_id=social_app.client_id,
            client_secret=social_app.secret,
            token_uri='https://oauth2.googleapis.com/token'
        )

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        service = get_gmail_service(credentials)
        
        # Fetch received emails
        query_received = 'label:inbox -label:unread'  # Query to get only received and read emails
        messages_received = service.users().messages().list(userId='me', q=query_received, maxResults=10).execute()

        # Fetch sent emails
        query_sent = 'label:sent'  # Query to get sent emails
        messages_sent = service.users().messages().list(userId='me', q=query_sent, maxResults=10).execute()

        # Process each received email
        for message in messages_received.get('messages', []):
            email_data = service.users().messages().get(userId='me', id=message['id']).execute()
            email_snippet = email_data['snippet']
            email_instance = Email.objects.create(user=user, content=email_snippet, is_received=True)
            received_emails.append(email_instance)  # Append the email to the received_emails list

        # Process each sent email
        for message in messages_sent.get('messages', []):
            email_data = service.users().messages().get(userId='me', id=message['id']).execute()
            email_snippet = email_data['snippet']
            email_instance = Email.objects.create(user=user, content=email_snippet, is_received=False)
            sent_emails.append(email_instance)  # Append the email to the sent_emails list

    except SocialToken.DoesNotExist:
        return redirect('/accounts/google/login/')  # Redirect to login if no token is found
    except Exception as e:
        print(f"An error occurred: {e}")
        return HttpResponse(f"An error occurred: {str(e)}", status=500)

    context = {
        'received_emails': received_emails,
        'sent_emails': sent_emails
    }
    return render(request, 'read_email_list.html', context)
# )


@login_required
def analyze_sentiment(request):
    """Analyze the sentiment of the provided email content."""
    if request.method == 'POST':
        email_content = request.POST.get('email_content', '')
        if email_content:  # Ensure content is not empty
            # Perform sentiment analysis using [TextBlob](https://textblob.readthedocs.io/en/dev/)
            blob = TextBlob(email_content)
            sentiment = blob.sentiment.polarity  # Get sentiment polarity (range from -1 to 1)

            # Determine sentiment label based on polarity score
            if sentiment > 0:
                sentiment_label = 'Positive'
            elif sentiment < 0:
                sentiment_label = 'Negative'
            else:
                sentiment_label = 'Neutral'

            # Save the sentiment analysis result to the database
            email_instances = Email.objects.filter(content=email_content, user=request.user)
            if email_instances.exists():
                for email_instance in email_instances:
                    SentimentAnalysisResult.objects.create(
                        email=email_instance,
                        sentiment_label=sentiment_label,
                        sentiment_score=sentiment
                    )

                # Pass the sentiment data to the template for display
                context = {
                    'email_content': email_content,
                    'sentiment': sentiment_label,
                    'sentiment_score': sentiment
                }
                return render(request, 'sentiment_result.html', context)

            return HttpResponse("No matching email found.", status=404)  # If no matching email

        return HttpResponse("No content provided for sentiment analysis.", status=400)  # Handle empty content

    return redirect('home')  # Redirect if not a POST request

# views.py

import logging
from django import forms
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

# Set up logger
logger = logging.getLogger(__name__)

class EmailForm(forms.Form):
    recipient = forms.EmailField(label='Recipient Email')
    subject = forms.CharField(max_length=100)
    message = forms.CharField(widget=forms.Textarea)

@login_required
def send_email(request):
    if request.method == 'POST':
        form = EmailForm(request.POST)
        if form.is_valid():
            recipient = form.cleaned_data['recipient']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            try:
                send_mail(subject, message, request.user.email, [recipient])
                return redirect('home')
            except Exception as e:
                logger.error(f"Error sending email: {e}")
                return render(request, 'send_email.html', {'form': form, 'error': 'Error sending email. Please try again.'})
    else:
        form = EmailForm()
    return render(request, 'send_email.html', {'form': form})

API_KEY = 'AIzaSyCXMo33miiJ1R3TOFDRTD96RsAe7gdlN8o'
API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent'

# Define predefined responses for the chatbot
PREDEFINED_RESPONSES = {
    'hello': 'Hi there! How can I assist you today?',
    'bye': 'Goodbye! Have a great day!',
    # Add more predefined responses as needed
}

def chatbot(request):
    if request.method == 'POST':
        user_message = request.POST.get('message')
        conversation_history = request.session.get('conversation_history', [])

        # Append user message to the conversation history
        conversation_history.append(f"input: {user_message}")
        bot_reply = PREDEFINED_RESPONSES.get(user_message.lower(), None)  # Case insensitive match

        if not bot_reply:
            # Make a request to the Google API if the message is not predefined
            headers = {'Content-Type': 'application/json'}
            messages = [{'text': message} for message in conversation_history]

            data = {'contents': [{'parts': messages}]}

            try:
                response = requests.post(f'{API_URL}?key={API_KEY}', headers=headers, json=data)
                response.raise_for_status()
                api_response = response.json()
                bot_reply = api_response['candidates'][0]['content']['parts'][0]['text']
                bot_reply = '. '.join(bot_reply.split('. ')[:3])  # Limit response to 3 sentences
            except requests.RequestException as e:
                print(f"API request error: {e}")
                bot_reply = 'Sorry, there was an error processing your request.'

        # Append bot reply to conversation history
        conversation_history.append(f"output: {bot_reply}")
        request.session['conversation_history'] = conversation_history

        # Return the bot reply as a JSON response
        return JsonResponse({'reply': bot_reply})

    return render(request, 'chatbot.html')

from django.http import FileResponse
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

import tempfile
import os
from django.http import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from matplotlib import pyplot as plt
from .models import Email  # Adjust the import as necessary

@login_required
def download_report(request):
    # Generate the bar chart
    sentiment_counts = {
        'positive': Email.objects.filter(user=request.user, sentiment_results__sentiment_label='Positive').count(),
        'negative': Email.objects.filter(user=request.user, sentiment_results__sentiment_label='Negative').count(),
        'neutral': Email.objects.filter(user=request.user, sentiment_results__sentiment_label='Neutral').count()
    }

    # Create a bar chart using matplotlib
    labels = ['Positive', 'Negative', 'Neutral']
    counts = [sentiment_counts['positive'], sentiment_counts['negative'], sentiment_counts['neutral']]
    fig, ax = plt.subplots()
    ax.bar(labels, counts, color=['#4CAF50', '#F44336', '#FFC107'])
    ax.set_xlabel('Sentiment')
    ax.set_ylabel('Number of Emails')
    ax.set_title('Email Sentiment Analysis Report')

    # Create a temporary file to save the chart
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmpfile:
        plt.savefig(tmpfile.name, format='png')
        plt.close(fig)  # Close the figure to release memory

        # Create PDF using ReportLab
        pdf_io = BytesIO()
        pdf = canvas.Canvas(pdf_io, pagesize=letter)
        pdf.drawString(100, 750, "Email Sentiment Analysis Report")

        # Add the chart image to the PDF
        pdf.drawImage(tmpfile.name, 100, 500, width=400, height=300)

        pdf.save()
        pdf_io.seek(0)

    # Clean up the temporary file
    os.remove(tmpfile.name)

    # Return the PDF as a response
    return FileResponse(pdf_io, as_attachment=True, filename='sentiment_report.pdf')


