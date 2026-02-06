import os
import sys
import glob
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
from django.conf import settings
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moodleroster.settings")
django.setup()

from roster.classroom_api import upload_screenshot_329
from roster.models import Workplace

def test_screenshot_upload():
    print("Testing screenshot upload...")
    
    workplace_id = "1"
    
    # Cleanup previous run
    dir_path = os.path.join(settings.BASE_DIR, 'data', 'screenshots', workplace_id)
    if os.path.exists(dir_path):
        for f in glob.glob(os.path.join(dir_path, "*.png")):
            os.remove(f)
            
    factory = RequestFactory()
    
    # upload 105 files
    for i in range(105):
        content = b"fake image content"
        
        # Testing Rotation Logic specially:
        # I'll create 105 dummy files manually
        if i < 105:
            fname = f"test_{i:03d}.png"
            fpath = os.path.join(dir_path, fname)
            os.makedirs(dir_path, exist_ok=True)
            with open(fpath, 'wb') as f:
                f.write(b'test')
            # Set mtime to ensure order
            t = time.time() - (1000 - i) # older files first
            os.utime(fpath, (t, t))
            
    # Now call the view with one more file to trigger rotation check
    print("Created 105 manual files. Calling view to upload one more...")
    
    image = SimpleUploadedFile("upload.png", b"new content", content_type="image/png")
    request = factory.post(
        f'/api/classrooms/329/workplaces/{workplace_id}/screenshot/',
        {'file': image}
    )
    
    response = upload_screenshot_329(request, workplace_id)
    
    if response.status_code != 200:
        print(f"FAILED: Status {response.status_code}")
        print(response.content)
        return
        
    print("Upload successful.")
    
    # Check rotation
    files = glob.glob(os.path.join(dir_path, "*.png"))
    print(f"Files count: {len(files)}")
    
    if len(files) > 100:
        print("FAILED: Rotation did not work, found > 100 files.")
    elif len(files) == 100:
        print("SUCCESS: Count is 100.")
    else:
        print(f"WARNING: Count is {len(files)}, expected ~100 if we had 105 before?")
        # If I created 105, and view added 1 -> 106. View keeps last 100.
        # So should be 100.
        
    # Check DB
    w = Workplace.objects.get(workplace_number=int(workplace_id))
    print(f"DB Record: {w.workplace_number}, {w.last_screenshot_filename}, {w.last_screenshot_at}")

    # Test Regex Extraction
    print("\nTesting Regex extraction (user-5)...")
    request = factory.post(
        f'/api/classrooms/329/workplaces/user-5/screenshot/',
        {'file':  SimpleUploadedFile("rx.png", b"rx", content_type="image/png")}
    )
    # Check if folder '5' exists and has files (we reused '1' but now '5')
    resp2 = upload_screenshot_329(request, 'user-5')
    if resp2.status_code == 200:
        print("Regex upload success.")
        # Check folder '5'
        if os.path.exists(os.path.join(settings.BASE_DIR, 'data', 'screenshots', '5')):
            print("Folder '5' exists.")
    else:
        print(f"Regex upload FAILED: {resp2.content}")
        
    # Test Fallback
    print("\nTesting Fallback (teacher_pc)...")
    request = factory.post(
        f'/api/classrooms/329/workplaces/teacher_pc/screenshot/',
        {'file':  SimpleUploadedFile("fb.png", b"fb", content_type="image/png")}
    )
    resp3 = upload_screenshot_329(request, 'teacher_pc')
    if resp3.status_code == 200:
        print("Fallback upload success.")
        if os.path.exists(os.path.join(settings.BASE_DIR, 'data', 'screenshots', 'teacher_pc')):
            print("Folder 'teacher_pc' exists.")
    else:
        print(f"Fallback upload FAILED: {resp3.content}")
    
if __name__ == "__main__":
    test_screenshot_upload()
