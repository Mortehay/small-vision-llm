import os
from PIL import Image
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

from helpers import connect_camera, camera_src

MODEL_ID = "Qwen/Qwen2-VL-2B-Instruct"
DEVICE = "cpu" if torch.cuda.is_available() else "cpu"

print(f"Loading Qwen2-VL on {DEVICE}...")
model = Qwen2VLForConditionalGeneration.from_pretrained(
    MODEL_ID, torch_dtype="auto", device_map="auto"
)
processor = AutoProcessor.from_pretrained(MODEL_ID)

cap = connect_camera()

if not cap.isOpened():
    print(f"Cannot open source: {camera_src}")
    exit(1)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break

    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    messages = [
        {
            "role": "user",
            "content": [{"type": "image", "image": image}, {"type": "text", "text": "Who is in the video?"}],
        }
    ]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, _ = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, padding=True, return_tensors="pt").to(DEVICE)

    generated_ids = model.generate(**inputs, max_new_tokens=50)
    output_text = processor.batch_decode(generated_ids, skip_special_tokens=True)
    print(f"Qwen2-VL: {output_text[0]}")

cap.release()