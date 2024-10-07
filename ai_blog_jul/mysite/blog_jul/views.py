# myapp/views.py


from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from urllib.error import HTTPError, URLError
import json
import yt_dlp as youtube_dl  # Use yt_dlp instead of youtube_dl
from pytube.exceptions import PytubeError
import ffmpeg
import os
import assemblyai as aai
import openai
from .models import BlogPost
import logging


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing request data: {e}")
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        try:
            title = yt_title(yt_link)
        except Exception as e:
            logger.error(f"Error getting YouTube title: {e}")
            return JsonResponse({'error': 'Failed to get YouTube title'}, status=500)

        try:
            transcription = get_transcription(yt_link)
            if not transcription:
                return JsonResponse({'error': "Failed to get transcript"}, status=500)
        except Exception as e:
            logger.error(f"Error getting transcription: {e}")
            return JsonResponse({'error': 'Failed to get transcription'}, status=500)

        try:
            blog_content = generate_blog_from_transcription(transcription)
            if not blog_content:
                return JsonResponse({'error': "Failed to generate blog article"}, status=500)
        except Exception as e:
            logger.error(f"Error generating blog content: {e}")
            return JsonResponse({'error': 'Failed to generate blog article'}, status=500)

        try:
            new_blog_article = BlogPost.objects.create(
                user=request.user,
                youtube_title=title,
                youtube_link=yt_link,
                generated_content=blog_content,
            )
            new_blog_article.save()
        except Exception as e:
            logger.error(f"Error saving blog article to the database: {e}")
            return JsonResponse({'error': 'Failed to save blog article'}, status=500)

        return JsonResponse({'content': blog_content})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


def yt_title(link):
    try:
        ydl_opts = {'quiet': True, 'skip_download': True, 'force_generic_extractor': True}
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(link, download=False)
            return info_dict.get('title', 'No title found')
    except Exception as e:
        logger.error(f"Error getting YouTube title: {e}")
        raise

def download_audio(link):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '/Users/salah/Desktop/Web-Dev/ai_blog_jul/mysite/media/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'noplaylist': True,  # Ensure only one video is processed
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(link, download=True)
            # Assume the first file in the result is the desired audio
            audio_file_path = ydl.prepare_filename(result)
            audio_file_path = audio_file_path.replace('.webm', '.mp3')  # Adjust as needed
            if not os.path.isfile(audio_file_path):
                raise FileNotFoundError(f"Audio file not found after download: {audio_file_path}")
            return audio_file_path
    except Exception as e:
        logger.error(f"Error downloading audio: {e}")
        return None

def get_transcription(audio_file_path):
    try:
        with open(audio_file_path, 'rb') as audio_file:
            response = openai.Audio.transcribe(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
            return response['text']
    except FileNotFoundError:
        logger.error(f"Audio file not found: {audio_file_path}")
        return None
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        return None

def generate_blog_from_transcription(transcription):
    if not transcription:
        logger.error("No transcription provided.")
        return None

    try:
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=f"Based on the following transcript from a YouTube video, write a comprehensive blog article. Write it based on the transcript, but don't make it look like a YouTube video. Make it look like a proper blog article:\n\n{transcription}\n\nArticle:",
            max_tokens=1000,
            temperature=0.7
        )
        generated_content = response.choices[0].text.strip()
        return generated_content
    except openai.OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
    except Exception as e:
        logger.error(f"Error generating blog content: {e}")

    return None

def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})
        
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message':error_message})
        else:
            error_message = 'Password do not match'
            return render(request, 'signup.html', {'error_message':error_message})
        
    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')




# from django.contrib.auth.models import User
# from django.contrib.auth import authenticate, login, logout
# from django.shortcuts import render, redirect
# from django.contrib.auth.decorators import login_required
# from django.views.decorators.csrf import csrf_exempt
# from django.http import JsonResponse
# from django.conf import settings
# import json
# import os
# from pytube import YouTube
# import assemblyai as aai
# import openai
# from .models import BlogPost
# import environ

# # Load environment variables
# env = environ.Env()
# environ.Env.read_env()

# # API keys from environment variables
# ASSEMBLYAI_API_KEY = env('4915ae210826448f8a68576e3b0130e8')
# OPENAI_API_KEY = env('sk-None-aJJnokyNjqS2gpgDsZm7T3BlbkFJCO2hrIVxT0OBU13I0xhF')

# @login_required
# def index(request):
#     return render(request, 'index.html')

# @csrf_exempt
# def generate_blog(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             yt_link = data['link']
#         except (KeyError, json.JSONDecodeError):
#             return JsonResponse({'error': 'Invalid data sent'}, status=400)

#         try:
#             # Get YouTube title
#             title = yt_title(yt_link)

#             # Get transcript
#             transcription = get_transcription(yt_link)
#             if not transcription:
#                 return JsonResponse({'error': "Failed to get transcript"}, status=500)

#             # Generate blog content
#             blog_content = generate_blog_from_transcription(transcription)
#             if not blog_content:
#                 return JsonResponse({'error': "Failed to generate blog article"}, status=500)

#             # Save blog article to database
#             new_blog_article = BlogPost.objects.create(
#                 user=request.user,
#                 youtube_title=title,
#                 youtube_link=yt_link,
#                 generated_content=blog_content,
#             )

#             return JsonResponse({'content': blog_content})

#         except Exception as e:
#             return JsonResponse({'error': str(e)}, status=500)

#     return JsonResponse({'error': 'Invalid request method'}, status=405)

# def yt_title(link):
#     try:
#         yt = YouTube(link)
#         return yt.title
#     except Exception as e:
#         return f"Error retrieving title: {e}"

# def download_audio(link):
#     try:
#         yt = YouTube(link)
#         video = yt.streams.filter(only_audio=True).first()
#         out_file = video.download(output_path=settings.MEDIA_ROOT)
#         base, ext = os.path.splitext(out_file)
#         new_file = base + '.mp3'
#         os.rename(out_file, new_file)
#         return new_file
#     except Exception as e:
#         return f"Error downloading audio: {e}"

# def get_transcription(link):
#     audio_file = download_audio(link)
#     if audio_file.startswith("Error"):
#         return None

#     aai.settings.api_key = ASSEMBLYAI_API_KEY

#     try:
#         transcriber = aai.Transcriber()
#         transcript = transcriber.transcribe(audio_file)
#         return transcript.text
#     except Exception as e:
#         return f"Error transcribing audio: {e}"

# def generate_blog_from_transcription(transcription):
#     openai.api_key = OPENAI_API_KEY

#     prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article. Transform the transcript into a coherent blog post:\n\n{transcription}\n\nArticle:"

#     try:
#         response = openai.Completion.create(
#             model="text-davinci-003",
#             prompt=prompt,
#             max_tokens=1000
#         )
#         return response.choices[0].text.strip()
#     except Exception as e:
#         return f"Error generating blog content: {e}"

# def blog_list(request):
#     blog_articles = BlogPost.objects.filter(user=request.user)
#     return render(request, "all-blogs.html", {'blog_articles': blog_articles})

# def blog_details(request, pk):
#     try:
#         blog_article_detail = BlogPost.objects.get(id=pk)
#         if request.user == blog_article_detail.user:
#             return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
#         else:
#             return redirect('/')
#     except BlogPost.DoesNotExist:
#         return redirect('/')

# def user_login(request):
#     if request.method == 'POST':
#         username = request.POST['username']
#         password = request.POST['password']

#         user = authenticate(request, username=username, password=password)
#         if user is not None:
#             login(request, user)
#             return redirect('/')
#         else:
#             error_message = "Invalid username or password"
#             return render(request, 'login.html', {'error_message': error_message})

#     return render(request, 'login.html')

# def user_signup(request):
#     if request.method == 'POST':
#         username = request.POST['username']
#         email = request.POST['email']
#         password = request.POST['password']
#         repeatPassword = request.POST['repeatPassword']

#         if password == repeatPassword:
#             try:
#                 user = User.objects.create_user(username, email, password)
#                 user.save()
#                 login(request, user)
#                 return redirect('/')
#             except Exception as e:
#                 error_message = f'Error creating account: {e}'
#                 return render(request, 'signup.html', {'error_message': error_message})
#         else:
#             error_message = 'Passwords do not match'
#             return render(request, 'signup.html', {'error_message': error_message})

#     return render(request, 'signup.html')

# def user_logout(request):
#     logout(request)
#     return redirect('/')
