import cv2
from PIL import Image
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

MODEL_ID = "vikhyatk/moondream2"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Loading Moondream2 on {DEVICE}...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, 
    trust_remote_code=True,
    torch_dtype=torch.float16
).to(DEVICE)
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break

    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    # Moondream has a specialized 'answer_question' method
    enc_image = model.encode_image(image)
    answer = model.answer_question(enc_image, "What is the most prominent object?", tokenizer)
    
    print(f"Moondream: {answer}")

cap.release()