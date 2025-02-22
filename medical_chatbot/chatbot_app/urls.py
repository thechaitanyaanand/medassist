# chatbot_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("upload/", views.upload_document, name="upload"),
    path("ask/", views.ask_question, name="ask"),
    path("documents/", views.view_documents, name="documents"),
    path("verify-otp/<str:patient_id>/", views.verify_otp, name="verify_otp"),
]
