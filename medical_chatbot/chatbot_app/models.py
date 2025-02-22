from django.db import models

# Create your models here.

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    patient_id = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"{self.patient_id} ({self.user.username})"

class UploadedDocument(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='uploads/')
    file_type = models.CharField(max_length=50)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    raw_extracted_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.file.name

class ProcessedData(models.Model):
    document = models.OneToOneField(UploadedDocument, on_delete=models.CASCADE, related_name='processed_data')
    segmentation_text = models.TextField()
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Processed data for {self.document.file.name}"

class AccessRequest(models.Model):
    requestor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='access_requests')
    patient_profile = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='access_requests')
    otp_code = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Access request for {self.patient_profile.patient_id} by {self.requestor.username}"
