from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth import get_user_model, authenticate, login, logout
import json
from rest_framework.decorators import api_view
import openai
from django.http import StreamingHttpResponse
import re
import uuid
from django_ratelimit.decorators import ratelimit
from newspaper import Article

def break_into_paragraphs(text, num_sentences=1):
    if '\n' in text:
        return text  # Leave the text as it is if it already contains newline characters
    
    sentences = re.split(r'(?<=[.!?])\s+', text)
    print(sentences)
    paragraphs = []

    for i in range(0, len(sentences), num_sentences):
        paragraph = ' '.join(sentences[i:i+num_sentences])
        paragraphs.append(paragraph)

    return '/n/n'.join(paragraphs)

def get_article_data(request):
    url = request.GET.get('url', '')

    if url:
        article = Article(url, language="en")
        article.download()
        article.parse()

        # Decide how to format text based on its content
        if '\n' in article.text:
            formatted_text = article.text.replace("\n", "/n")
        else:
            formatted_text = break_into_paragraphs(article.text)
        
        data = {
            "title": article.title,
            "text": formatted_text,  # Replacing \n with /n
            "summary": article.summary,
            "publish_date": str(article.publish_date),
            "authors": article.authors,
            "keywords": article.keywords,
        }
        return JsonResponse(data)
    
    return JsonResponse({"error": "Invalid URL"})


User = get_user_model()


def signup_view(request):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))

        username = data.get('username')
        password = data.get('password')
        first_name = data.get('first_name')
        last_name = data.get('last_name')

        if username and 5 <= len(username) <= 10 and username.isalnum():
            user = User.objects.create_user(
                username=username, password=password, first_name=first_name, last_name=last_name)
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'failure', 'error': 'Invalid username'})


def login_view(request):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))

        username = data.get('username')
        password = data.get('password')
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return JsonResponse({'status': 'success', 'first_name': user.first_name})
        else:
            return JsonResponse({'status': 'failure', 'error': 'Invalid credentials'})


def logout_view(request):
    logout(request)
    return JsonResponse({'status': 'logged out'})



session_data = {}  # e.g. {'some-session-id': {'articleText': 'some text', 'processed': False}}

# @ratelimit(key='ip', rate='50/m')  # Allows 50 requests per minute per IP
@api_view(['POST'])
def store_text(request):
    if request.method == 'POST':
        was_limited = getattr(request, 'limited', False)
        if was_limited:
            return JsonResponse({'error': 'Rate limit exceeded'}, status=429)
        
        data = json.loads(request.body.decode('utf-8'))
        articleText = data.get('articleText', '')
        
        session_id = str(uuid.uuid4())
        session_data[session_id] = {'articleText': articleText, 'processed': False}
        
        return JsonResponse({'sessionId': session_id})

def process_request(request, session_id, question_prefix, stream=True):
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        return StreamingHttpResponse("Rate limit exceeded", content_type='text/event-stream', status=429)
    
    session_info = session_data.get(session_id, {})
    articleText = session_info.get('articleText', '')
    
    if session_info.get('processed', False):
        return JsonResponse({'error': 'This session ID has already been processed.'})
    
    session_data[session_id]['processed'] = True
    question = f"{question_prefix}: {articleText}"
    
    def event_stream():
        API_KEY = os.environ.get('key')
        openai.api_key = API_KEY
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=[{"role": "user", "content": question}],
            temperature=0,
            stream=stream
        )
        
        for chunk in response:
            chunk_str = json.dumps(chunk)
            data = json.loads(chunk_str)
            choices = data.get("choices", [])
            
            for choice in choices:
                if "content" in choice.get("delta", {}):
                    content = choice["delta"]["content"]
                    if "\n" in content:
                        content = content.replace("\n", "/n")
                    yield f"data: {content}\n\n"

        yield "event: done\ndata: \n\n"
    
    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')

def process_keyword_request(request, session_id, question_prefix, stream=True):
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        return StreamingHttpResponse("Rate limit exceeded", content_type='text/event-stream', status=429)
    
    session_info = session_data.get(session_id, {})
    articleText = session_info.get('articleText', '')
    
    if session_info.get('processed', False):
        return JsonResponse({'error': 'This session ID has already been processed.'})
    
    session_data[session_id]['processed'] = True
    question = f"{question_prefix}: {articleText}"
    
    def event_stream():
        API_KEY = os.environ.get('key')
        openai.api_key = API_KEY
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=[{"role": "user", "content": question}],
            temperature=0,
            stream=stream
        )
        
        for chunk in response:
            chunk_str = json.dumps(chunk)
            data = json.loads(chunk_str)
            choices = data.get("choices", [])
            
            for choice in choices:
                if "content" in choice.get("delta", {}):
                    content = choice["delta"]["content"]
                    if "\n" in content:
                        content = content.replace("\n", "/n")
                    yield f"data: {content}\n\n"

        yield "event: done\ndata: \n\n"
    
    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')

# @ratelimit(key='ip', rate='50/m')
def Summary(request, session_id):
    return process_request(request, session_id, "Summarize this text")

# @ratelimit(key='ip', rate='50/m')
def Keywords(request, session_id):
    return process_keyword_request(request, session_id, "Top 5 Proper nouns")
