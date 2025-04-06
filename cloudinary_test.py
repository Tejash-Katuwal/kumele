import cloudinary
import cloudinary.uploader
import os

cloudinary.config(
    cloud_name= "dostiek8h",
    api_key="441397572511426",
    api_secret="SLKq7Ned7ULfz1LoMxWQztvCPms"
)

# Test upload
result = cloudinary.uploader.upload("D:\\Projects\\kumele\\kumele_project\\media\\qr_codes\\h13578810@gmail.com_qr.png")
print(result['secure_url'])