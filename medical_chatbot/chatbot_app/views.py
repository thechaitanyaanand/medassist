from django.shortcuts import render
import os


# Create your views here.

# chatbot_app/views.py

import os
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required

from .forms import DocumentUploadForm, QuestionForm
from .utils import (
    extract_text_from_pdf,
    extract_text_from_image,
    extract_dicom_metadata,
    run_segmentation,  # This calls our nnU-Net wrapper
    add_document,
    search_documents,
    answer_medical_query,
)
from .models import UploadedDocument, ProcessedData, PatientProfile, AccessRequest

# Ensure the uploads directory exists
UPLOAD_DIR = os.path.join(settings.BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@login_required
def home(request):
    return render(request, "chatbot_app/home.html")

@login_required
def upload_document(request):
    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            patient_id = form.cleaned_data["patient_id"]
            uploaded_file = request.FILES["file"]
            file_path = os.path.join(settings.BASE_DIR, "uploads", uploaded_file.name)
            
            # Save file locally
            with open(file_path, "wb+") as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # Use existing PatientProfile if it exists; otherwise, create one.
            try:
                profile = PatientProfile.objects.get(user=request.user)
                # Optional: Verify that the patient_id matches; if not, decide whether to update it.
                if profile.patient_id != patient_id:
                    # For example, you might update it or log a warning.
                    profile.patient_id = patient_id
                    profile.save()
            except PatientProfile.DoesNotExist:
                profile = PatientProfile.objects.create(user=request.user, patient_id=patient_id)
            
            # Process the file to extract text/insights
            extracted_text = ""
            fname = uploaded_file.name.lower()
            if fname.endswith(".pdf"):
                extracted_text = extract_text_from_pdf(file_path)
                file_type = "pdf"
            elif fname.endswith((".png", ".jpg", ".jpeg", ".tiff")):
                ocr_text = extract_text_from_image(file_path)
                segmentation_text = run_segmentation(file_path)
                extracted_text = ocr_text + "\n" + segmentation_text
                file_type = "image_scan"
            elif fname.endswith(".dcm"):
                meta = extract_dicom_metadata(file_path)
                dicom_text = " | ".join(f"{k}: {v}" for k, v in meta.items())
                segmentation_text = run_segmentation(file_path)
                extracted_text = dicom_text + "\n" + segmentation_text
                file_type = "dicom"
                # Optionally update metadata with DICOM info
            else:
                return HttpResponse("Unsupported file type.", status=400)
            
            # Save the document in the database
            doc = UploadedDocument.objects.create(
                patient=profile,
                file=uploaded_file,
                raw_extracted_text=extracted_text,
                file_type=file_type
            )
            if file_type in ["image_scan", "dicom"]:
                ProcessedData.objects.create(
                    document=doc,
                    segmentation_text=segmentation_text
                )
            
            return render(request, "chatbot_app/upload.html", {"form": form, "message": "Upload and processing successful."})
    else:
        form = DocumentUploadForm()
    return render(request, "chatbot_app/upload.html", {"form": form})


@login_required
def ask_question(request):
    answer = None
    context_documents = []
    if request.method == "POST":
        form = QuestionForm(request.POST)
        if form.is_valid():
            patient_id = form.cleaned_data["patient_id"]
            question = form.cleaned_data["question"]
            try:
                profile = PatientProfile.objects.get(patient_id=patient_id)
                # If the logged-in user is not the owner, verify if they have temporary access via OTP.
                if profile.user != request.user:
                    access_requests = AccessRequest.objects.filter(
                        patient_profile=profile,
                        requestor=request.user,
                        is_verified=True,
                        valid_until__gte=datetime.now()
                    )
                    if not access_requests.exists():
                        return HttpResponse("Access denied. OTP verification required.", status=403)
            except PatientProfile.DoesNotExist:
                return HttpResponse("Patient data not found.", status=404)
            
            # Retrieve documents for the patient and build context
            docs = profile.documents.all()
            context = "\n---\n".join([doc.raw_extracted_text for doc in docs])
            answer = answer_medical_query(question, context)
            context_documents = docs
    else:
        form = QuestionForm()
    return render(request, "chatbot_app/ask.html", {"form": form, "answer": answer, "documents": context_documents})

@login_required
def view_documents(request):
    try:
        profile = PatientProfile.objects.get(user=request.user)
        documents = profile.documents.all()
    except PatientProfile.DoesNotExist:
        documents = []
    return render(request, "chatbot_app/documents.html", {"documents": documents})

@login_required
def verify_otp(request, patient_id):
    if request.method == "POST":
        otp_submitted = request.POST.get("otp")
        try:
            profile = PatientProfile.objects.get(patient_id=patient_id)
            access_req = AccessRequest.objects.filter(
                patient_profile=profile,
                requestor=request.user,
                is_verified=False
            ).first()
            if access_req and otp_submitted == access_req.otp_code:
                access_req.is_verified = True
                access_req.valid_until = datetime.now() + timedelta(hours=1)
                access_req.save()
                return HttpResponse("Access granted.")
            else:
                return HttpResponse("OTP verification failed.", status=403)
        except PatientProfile.DoesNotExist:
            return HttpResponse("Patient data not found.", status=404)
    return render(request, "chatbot_app/verify_otp.html", {"patient_id": patient_id})
