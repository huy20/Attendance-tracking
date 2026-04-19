import onnx
from onnxconverter_common import float16

print("Converting FP32 to FP16...")
# Load the ORIGINAL FP32 model
model = onnx.load("MobileFaceNet.onnx")

# Convert to Float16
model_fp16 = float16.convert_float_to_float16(model)

# Save the new model
onnx.save(model_fp16, "MobileFaceNet_fp16.onnx")
print("Success! Created: MobileFaceNet_fp16.onnx")