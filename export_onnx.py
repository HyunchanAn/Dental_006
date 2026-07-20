import os
from huggingface_hub import HfApi
from dental_core.core.onnx_exporter import export_yolov8_to_onnx, export_classifier_to_onnx

# NOTE: Adjust MODEL_TYPE to "yolo" or "classifier" based on this module's architecture
MODEL_TYPE = "yolo"
REPO_ID = "HyunchanAn/Dental_006"
PT_PATH = "weights/best.pt" # Update path if different

def main():
    if not os.path.exists(PT_PATH):
        print(f"[Dental_006] No .pt file found at {PT_PATH}.")
        return

    print(f"[Dental_006] Exporting {PT_PATH} to ONNX...")
    
    onnx_path = None
    if MODEL_TYPE == "yolo":
        onnx_path = export_yolov8_to_onnx(PT_PATH)
    else:
        # Implement dummy input for your specific classifier
        # export_classifier_to_onnx(model, dummy_input, output_path)
        pass
        
    if onnx_path and os.path.exists(onnx_path):
        print(f"[Dental_006] Uploading to HuggingFace {REPO_ID}...")
        api = HfApi()
        # Ensure you are logged in via `huggingface-cli login`
        try:
            api.upload_file(
                path_or_fileobj=onnx_path,
                path_in_repo="weights/best.onnx",
                repo_id=REPO_ID,
                repo_type="model"
            )
            print(f"[Dental_006] Upload successful. Deleting local weights to save space...")
            os.remove(PT_PATH)
            os.remove(onnx_path)
            print(f"[Dental_006] Cleaned up local disk.")
        except Exception as e:
            print(f"[Dental_006] Upload failed: {e}")

if __name__ == "__main__":
    main()
