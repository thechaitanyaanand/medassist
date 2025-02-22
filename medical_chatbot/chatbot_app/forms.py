# chatbot_app/forms.py
from django import forms

class DocumentUploadForm(forms.Form):
    patient_id = forms.CharField(label="Patient ID", max_length=100)
    file = forms.FileField(label="Upload Document (PDF/Image/DICOM)")

class QuestionForm(forms.Form):
    patient_id = forms.CharField(label="Patient ID", max_length=100)
    question = forms.CharField(label="Your Question", widget=forms.Textarea)
