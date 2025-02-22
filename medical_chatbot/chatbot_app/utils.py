import os
import numpy as np
import pdfplumber
import cv2, pytesseract
import pydicom
from sentence_transformers import SentenceTransformer
import faiss
import openai

# Import the nnU-Net wrapper from the same package
from .nnunet_wrapper import segment_medical_scan

# Initialize SentenceTransformer (embedding size 384 for the model)
embed_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
embedding_dim = 384

# Global dictionary to hold user-specific data
# Structure: { patient_id: { "faiss_index": <FAISS index>, "doc_metadata": [list of dicts] } }
user_data = {}

# Configure OpenAI to use your locally run DeepSeek model.
# Update the api_base if you're using a non-default port (e.g., "http://localhost:11435")
openai.api_key = os.getenv("DEEPSEEK_API_KEY", "dummy_key")
openai.api_base = "http://localhost:11435"  # Adjust this to your actual port if different

# ----------------- Extraction Functions -----------------
def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {e}")
    return text

def extract_text_from_image(image_path: str) -> str:
    try:
        img = cv2.imread(image_path)
        if img is None:
            return ""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return pytesseract.image_to_string(gray)
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return ""

def extract_dicom_metadata(dicom_path: str) -> dict:
    try:
        dicom = pydicom.dcmread(dicom_path)
        metadata = {
            "PatientName": str(dicom.get("PatientName", "Unknown")),
            "Modality": dicom.get("Modality", "Unknown"),
            "StudyDate": dicom.get("StudyDate", "Unknown"),
            "StudyDescription": dicom.get("StudyDescription", "Not Available")
        }
        return metadata
    except Exception as e:
        print(f"Error processing DICOM {dicom_path}: {e}")
        return {}

# ----------------- nnU-Net Integration -----------------
def run_segmentation(file_path: str) -> str:
    """
    Run nnU-Net inference on the given medical scan and return a textual summary.
    This uses the nnU-Net wrapper function. In production, replace the dummy output
    with your actual nnU-Net integration code.
    """
    return segment_medical_scan(file_path)

# ----------------- User-Specific Embedding & Indexing Functions -----------------
def get_user_index(patient_id: str):
    """
    Ensure that a FAISS index and a metadata list exist for the given patient.
    """
    if patient_id not in user_data:
        user_data[patient_id] = {
            "faiss_index": faiss.IndexFlatL2(embedding_dim),
            "doc_metadata": []
        }
    return user_data[patient_id]["faiss_index"], user_data[patient_id]["doc_metadata"]

def embed_text(text: str) -> np.ndarray:
    return embed_model.encode(text)

def add_document(text: str, metadata: dict):
    patient_id = metadata.get("patient_id")
    if not patient_id:
        print("No patient ID provided in metadata.")
        return
    index, doc_metadata = get_user_index(patient_id)
    embedding = embed_text(text)
    embedding = np.array([embedding]).astype('float32')
    index.add(embedding)
    doc_metadata.append(metadata)

def search_documents(query: str, patient_id: str, k: int = 3):
    index, doc_metadata = get_user_index(patient_id)
    query_vec = embed_text(query)
    query_vec = np.array([query_vec]).astype('float32')
    distances, indices = index.search(query_vec, k)
    results = []
    for idx in indices[0]:
        if idx < len(doc_metadata):
            results.append(doc_metadata[idx])
    return results

# ----------------- DeepSeek Inference Function -----------------
def answer_medical_query(query: str, context: str) -> str:
    messages = [
        {"role": "system", "content": "You are a medical assistant that provides answers based solely on the provided patient data."},
        {"role": "user", "content": f"Patient data:\n{context}\n\nQuestion: {query}"}
    ]
    try:
        response = openai.ChatCompletion.create(
            model="deepseek-r1:7b",  # Ensure this matches the running model's identifier
            messages=messages,
            temperature=0.2,
            stream=False
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error during local model inference: {e}")
        return "Sorry, an error occurred while processing your query."

