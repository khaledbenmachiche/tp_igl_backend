from rest_framework import permissions
from django.core.files.base import ContentFile
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
import io
import os
from .forms import ArticleUploadForm
from .models import Article,UploadedArticle
from .serializers import ArticleSerializer
from zipfile import ZipFile
import requests
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from rest_framework.permissions import AllowAny , IsAuthenticated
from .CustomPermissions import IsAdmin, IsModerator
from .utils import extract_drive_folder_id
from .scrapping.grobid_scrapper_manager import GrobidScrapperManager
from django.http import Http404
from rest_framework.exceptions import MethodNotAllowed
from drf_yasg.utils import swagger_auto_schema
from .google_drive.google_drive_api_handler import GoogleDriveAPIHandler
from django.conf import settings

class ArticleViewSet(ModelViewSet):
    serializer_class = ArticleSerializer
    queryset = Article.objects.all()
    google_drive_handler  = GoogleDriveAPIHandler(
            settings.CLIENT_SECRET_FILE,
            settings.API_NAME,
            settings.API_VERSION,
            settings.SCOPES,
        )
    
    @action(detail=False, methods=['get'], url_path='validated',permission_classes=(IsAuthenticated,))
    def get_validated_articles(self,request,*args,**kwargs):
        try:
            articles = Article.objects.filter(is_validated=True)
            serializer = ArticleSerializer(articles,many=True)
            return Response(serializer.data,status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'message': "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=False,methods=['get'],url_path='not_validated',permission_classes=(IsAuthenticated,IsModerator,))
    def get_not_validated_articles(self,request,*args,**kwargs):
        try:
            articles = Article.objects.filter(is_validated=False)
            serializer = ArticleSerializer(articles,many=True)
            return Response(serializer.data,status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'message': "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
    @action(detail=True,methods=['put'],url_path='validate',permission_classes=(IsAuthenticated,IsModerator,))
    def validate_article(self,request,*args,**kwargs):
        try:
            article = self.get_object()
            if article.is_validated:
                return Response({'message': 'Article already validated'}, status=status.HTTP_400_BAD_REQUEST)
            article.is_validated = True
            article.save()
            return Response({'message': 'Article validated successfully'}, status=status.HTTP_200_OK)
        except Http404:
            return Response({'message': 'Article not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e)
            return Response({'message': "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='upload-via-file',permission_classes=(IsAuthenticated,IsAdmin,))
    def upload_article_via_file(self, request, *args, **kwargs):
        try:
            if(request.FILES.get('file') is not None):
                form = ArticleUploadForm(request.POST, request.FILES)
                if form.is_valid():
                    instance = form.save()
                    fs = FileSystemStorage()
                    file_path = fs.path(instance.file.name)
                    
                    self.google_drive_handler.upload_file(file_name=instance.file.name, file_path=file_path, folder_id=settings.GOOGLE_DRIVE_SCRAPPING_FOLDER_ID)
                    
                    scrapper = GrobidScrapperManager(drive_manager=self.google_drive_handler)
                    scrapper.run_scrapper()
                    return Response({'message': 'Article uploaded successfully!'}, status=status.HTTP_201_CREATED)
                else:
                    return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({'message': "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='upload-via-zip',permission_classes=(IsAuthenticated,IsAdmin,))
    def upload_article_via_zip(self, request, *args, **kwargs):
        try:
            zip_file = request.FILES.get('file')
            if not zip_file.name.endswith('.zip'):
                return Response({'message': 'Please upload a zip file.'}, status=status.HTTP_400_BAD_REQUEST)
            
            with ZipFile(zip_file,'r') as zip:
                pdf_files = [file for file in zip.filelist if file.filename.lower().endswith('.pdf')]
                if not pdf_files:
                    return Response({'message': 'No PDF files found in the zip file.'}, status=status.HTTP_400_BAD_REQUEST)
                
                fs = FileSystemStorage()
                for file in pdf_files:
                    if file.filename.lower().endswith('.pdf'):
                        file_name = file.filename.split('/')[-1]
                        file_name = os.path.join('EchantillonsArticlesScrapping/' ,file_name)
                        file_content = ContentFile(zip.read(file))
                        file_name = fs.save(file_name, file_content)
                        file_path = fs.path(file_name)
                        self.google_drive_handler.upload_file(file_name=file_name, file_path=file_path, folder_id=settings.GOOGLE_DRIVE_SCRAPPING_FOLDER_ID)
                
                scrapper = GrobidScrapperManager(drive_manager=self.google_drive_handler)
                scrapper.run_scrapper()
            
            return Response({'message': 'Articles uploaded successfully'}, status=status.HTTP_201_CREATED)
                
        except Exception:
            return Response({'message': "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    
    @action(detail=False, methods=['post'], url_path='upload-via-url',permission_classes=(IsAuthenticated,IsAdmin,))
    def upload_article_via_url(self, request, *args, **kwargs):
        try:
            if request.data.get('url'):
                    pdf_url = request.data['url']
                    response = requests.get(pdf_url)
                    if response.status_code == 200:
                        file_name = pdf_url.split('/')[-1]
                        file_name = os.path.join('EchantillonsArticlesScrapping/' ,file_name)
                        file_content = ContentFile(response.content)
                        fs = FileSystemStorage()
                        file_name = fs.save(file_name, file_content)
                        file_path = fs.path(file_name)
                        self.google_drive_handler.upload_file(file_name=file_name, file_path=file_path, folder_id=settings.GOOGLE_DRIVE_SCRAPPING_FOLDER_ID)
                        scrapper = GrobidScrapperManager(drive_manager=self.google_drive_handler)
                        scrapper.run_scrapper()
                        return Response({'message': 'File downloaded and saved successfully'}, status=status.HTTP_201_CREATED)
                    else:
                        return Response({'message': 'File not found'}, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({'message': 'Please provide a url'}, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception:
            return Response({'message': "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
    @action(detail=False, methods=['post'], url_path='upload-via-drive',permission_classes=(IsAuthenticated,IsAdmin,))
    def upload_article_via_drive(self, request, *args, **kwargs):
        try:
            drive_url = request.data.get('url')
            if not drive_url:
                return Response({'message': 'Please provide a drive url'}, status=status.HTTP_400_BAD_REQUEST)
            if not drive_url.startswith('https://drive.google.com'):
                return Response({'message': 'Invalid drive url'}, status=status.HTTP_400_BAD_REQUEST)
        
            scrapper = GrobidScrapperManager(drive_manager=self.google_drive_handler, folder_id=extract_drive_folder_id(drive_url))
            scrapper.run_scrapper()
            return Response({'message': 'File downloaded and saved successfully'}, status=status.HTTP_201_CREATED)
        except Exception:
            return Response({'message': "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @swagger_auto_schema(auto_schema=None)
    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST")
