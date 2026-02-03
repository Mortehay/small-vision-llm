import cv2
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageTextToText

# Configuration
MODEL_ID = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Loading SmolVLM2 on {DEVICE}...")
processor = AutoProcessor.from_pretrained(MODEL_ID)
model = AutoModelForImageTextToText.from_pretrained(
    MODEL_ID, 
    torch_dtype=torch.bfloat16,
    _attn_implementation="eager" # AMD iGPU friendly
).to(DEVICE)

cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Process every 30th frame to save CPU/GPU cycles
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    messages = [
        {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "Describe the scene briefly."}]}
    ]
    
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(text=prompt, images=[image], return_tensors="pt").to(DEVICE)

    generated_ids = model.generate(**inputs, max_new_tokens=50)
    result = processor.batch_decode(generated_ids, skip_special_tokens=True)
    
    print(f"SmolVLM: {result[0].split('assistant')[-1]}")

cap.release()