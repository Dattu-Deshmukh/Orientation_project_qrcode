import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image
import io
import cv2
import numpy as np
import base64
import time

# ========================
# QR CODE DETECTION FUNCTIONS
# ========================

def detect_qr_with_opencv(image):
    """Try to detect QR code using OpenCV"""
    try:
        # Convert PIL image to OpenCV format
        img_array = np.array(image)
        
        # Initialize QR code detector
        qr_detector = cv2.QRCodeDetector()
        
        # Detect and decode QR code
        data, vertices_array, binary_qrcode = qr_detector.detectAndDecode(img_array)
        
        if data:
            return data
        return None
    except Exception as e:
        st.error(f"OpenCV detection error: {e}")
        return None

# ========================
# CUSTOM CAMERA COMPONENT
# ========================

def create_camera_component():
    """Create a custom camera component with rear camera support"""
    
    camera_html = """
    <div style="text-align: center; padding: 20px;">
        <video id="video" width="100%" height="400" style="border: 2px solid #4CAF50; border-radius: 10px; max-width: 500px;" autoplay></video>
        <br><br>
        <div style="margin: 10px;">
            <button onclick="switchCamera()" style="background-color: #2196F3; color: white; padding: 10px 20px; border: none; border-radius: 5px; margin: 5px; cursor: pointer;">
                📷 Switch Camera
            </button>
            <button onclick="captureImage()" style="background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; margin: 5px; cursor: pointer;">
                📸 Capture QR
            </button>
            <button onclick="toggleCamera()" id="toggleBtn" style="background-color: #FF9800; color: white; padding: 10px 20px; border: none; border-radius: 5px; margin: 5px; cursor: pointer;">
                ⏸️ Stop Camera
            </button>
        </div>
        <canvas id="canvas" width="500" height="400" style="display: none;"></canvas>
        <div id="result" style="margin-top: 20px; font-size: 16px;"></div>
    </div>

    <script>
    let video = document.getElementById('video');
    let canvas = document.getElementById('canvas');
    let context = canvas.getContext('2d');
    let currentStream = null;
    let facingMode = 'environment'; // Start with rear camera
    let isScanning = false;
    let cameraActive = false;

    // Start camera function
    async function startCamera() {
        try {
            if (currentStream) {
                currentStream.getTracks().forEach(track => track.stop());
            }

            const constraints = {
                video: {
                    facingMode: facingMode,
                    width: { ideal: 500 },
                    height: { ideal: 400 }
                }
            };

            currentStream = await navigator.mediaDevices.getUserMedia(constraints);
            video.srcObject = currentStream;
            cameraActive = true;
            document.getElementById('toggleBtn').innerHTML = '⏸️ Stop Camera';
            document.getElementById('result').innerHTML = '<div style="color: green;">📹 Camera active - Point at QR code and capture</div>';
            
            // Start continuous QR scanning
            startContinuousScanning();
            
        } catch (error) {
            console.error('Error accessing camera:', error);
            document.getElementById('result').innerHTML = '<div style="color: red;">❌ Camera access denied or not available</div>';
        }
    }

    // Switch between front and rear camera
    async function switchCamera() {
        facingMode = facingMode === 'environment' ? 'user' : 'environment';
        const cameraType = facingMode === 'environment' ? 'Rear' : 'Front';
        document.getElementById('result').innerHTML = `<div style="color: blue;">🔄 Switching to ${cameraType} camera...</div>`;
        await startCamera();
    }

    // Toggle camera on/off
    function toggleCamera() {
        if (cameraActive) {
            if (currentStream) {
                currentStream.getTracks().forEach(track => track.stop());
            }
            video.srcObject = null;
            cameraActive = false;
            isScanning = false;
            document.getElementById('toggleBtn').innerHTML = '▶️ Start Camera';
            document.getElementById('result').innerHTML = '<div style="color: gray;">📷 Camera stopped</div>';
        } else {
            startCamera();
        }
    }

    // Capture image function
    function captureImage() {
        if (!cameraActive) {
            document.getElementById('result').innerHTML = '<div style="color: red;">❌ Please start the camera first</div>';
            return;
        }

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0);
        
        // Convert to base64 and send to Streamlit
        const imageData = canvas.toDataURL('image/png');
        document.getElementById('result').innerHTML = '<div style="color: orange;">🔍 Processing image...</div>';
        
        // Send image data to Streamlit
        window.parent.postMessage({
            type: 'captured_image',
            data: imageData
        }, '*');
    }

    // Continuous QR scanning (optional - scans every 2 seconds)
    function startContinuousScanning() {
        if (isScanning) return;
        isScanning = true;
        
        setInterval(() => {
            if (cameraActive && video.videoWidth > 0) {
                // Auto-capture for continuous scanning (optional)
                // Uncomment the next line if you want automatic scanning every 2 seconds
                // captureImage();
            }
        }, 2000);
    }

    // Auto-start camera when page loads
    window.addEventListener('load', () => {
        setTimeout(startCamera, 1000);
    });

    // Handle page visibility change
    document.addEventListener('visibilitychange', () => {
        if (document.hidden && cameraActive) {
            // Page is hidden, stop camera to save resources
            if (currentStream) {
                currentStream.getTracks().forEach(track => track.stop());
            }
        } else if (!document.hidden && cameraActive) {
            // Page is visible again, restart camera
            startCamera();
        }
    });
    </script>
    """
    
    return camera_html

# ========================
# GOOGLE SHEETS CONNECTION
# ========================

@st.cache_resource
def init_google_sheets():
    """Initialize Google Sheets connection with caching"""
    try:
        scope = ["https://spreadsheets.google.com/feeds",
                 "https://www.googleapis.com/auth/drive"]
        
        # Try to load credentials from Streamlit secrets first
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # Fallback to local file
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
        client = gspread.authorize(creds)
        sheet = client.open("orientation_passes").sheet1
        return sheet
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        st.info("Please check your credentials configuration.")
        return None

def process_student_scan(qr_data, sheet):
    """Process the scanned student data"""
    try:
        records = sheet.get_all_records()
        found = False
        
        for i, row in enumerate(records, start=2):
            if str(row["ID"]) == str(qr_data):
                found = True
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Check current status
                entry_status = row.get("EntryStatus", "")
                exit_status = row.get("ExitStatus", "")
                
                # Mark entry
                if not entry_status or entry_status == "":
                    sheet.update_cell(i, 4, "Entered")  # EntryStatus column
                    sheet.update_cell(i, 5, now)        # EntryTime column
                    st.success(f"✅ **Entry marked** for **{row['Name']}** ({row['Branch']})")
                    st.balloons()
                    
                # Mark exit
                elif not exit_status or exit_status == "":
                    sheet.update_cell(i, 6, "Exited")   # ExitStatus column
                    sheet.update_cell(i, 7, now)        # ExitTime column
                    st.warning(f"🚪 **Exit marked** for **{row['Name']}** ({row['Branch']})")
                    
                # Already processed
                else:
                    st.info(f"ℹ️ **{row['Name']}** ({row['Branch']}) has already entered and exited.")
                    st.write("**Current Status:**")
                    st.write(f"• Entry: {row.get('EntryTime', 'Not recorded')}")
                    st.write(f"• Exit: {row.get('ExitTime', 'Not recorded')}")
                
                break
        
        if not found:
            st.error("❌ **Student ID not found** in records.")
            st.write("Please verify the QR code or contact the administrator.")
            
    except Exception as e:
        st.error(f"**Database Error:** {e}")
        st.write("Please try again or contact technical support.")

# ========================
# STREAMLIT UI
# ========================

def main():
    st.set_page_config(
        page_title="Orientation QR Scanner", 
        page_icon="📷", 
        layout="wide"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        color: #4CAF50;
        font-size: 2.5rem;
        margin-bottom: 1rem;
    }
    .instruction-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #4CAF50;
        margin: 1rem 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="main-header">🎓 Orientation QR Scanner</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="instruction-box">
    📌 <strong>Live Camera Instructions:</strong><br>
    1. Allow camera permissions when prompted<br>
    2. Use "Switch Camera" to toggle between front/rear camera<br>
    3. Point rear camera at QR code for best results<br>
    4. Click "Capture QR" when QR code is visible<br>
    5. Use manual entry if camera scanning fails
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize Google Sheets
    sheet = init_google_sheets()
    if not sheet:
        st.stop()
    
    # Create tabs for different input methods
    tab1, tab2 = st.tabs(["📹 Live Camera Scanner", "📝 Manual Entry"])
    
    with tab1:
        st.write("### 📹 Live Camera QR Scanner")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Display the custom camera component
            camera_component = create_camera_component()
            st.components.v1.html(camera_component, height=600)
        
        with col2:
            st.write("### 📋 Instructions")
            st.info("""
            **Camera Controls:**
            - 📷 **Switch Camera**: Toggle front/rear
            - 📸 **Capture QR**: Take photo to scan
            - ⏸️ **Stop Camera**: Turn off camera
            
            **Tips:**
            - Rear camera works best for QR codes
            - Ensure good lighting
            - Hold phone steady
            - QR code should fill most of the frame
            """)
            
            # Image processing area
            st.write("### 🔍 Scan Results")
            
            # Handle captured images via JavaScript postMessage
            captured_image = st.empty()
            scan_result = st.empty()
        
        # Handle image capture from JavaScript
        if 'captured_image_data' in st.session_state:
            try:
                # Decode base64 image
                image_data = st.session_state.captured_image_data
                if image_data.startswith('data:image'):
                    # Remove the data:image/png;base64, part
                    base64_data = image_data.split(',')[1]
                    image_bytes = base64.b64decode(base64_data)
                    
                    # Convert to PIL Image
                    img = Image.open(io.BytesIO(image_bytes))
                    
                    with col2:
                        st.image(img, caption="Captured Image", width=250)
                        
                        with st.spinner("🔍 Scanning for QR code..."):
                            qr_data = detect_qr_with_opencv(img)
                        
                        if qr_data:
                            st.success(f"📋 **Scanned ID:** {qr_data}")
                            process_student_scan(qr_data, sheet)
                        else:
                            st.error("⚠️ **No QR code detected** in the image.")
                            st.write("Try adjusting the camera angle or lighting.")
                
                # Clear the captured image from session state
                del st.session_state.captured_image_data
                
            except Exception as e:
                st.error(f"Error processing captured image: {e}")
    
    with tab2:
        st.write("### 📝 Manual Student ID Entry")
        st.info("Use this option if the camera scanner is not working properly.")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            manual_id = st.text_input(
                "Enter Student ID:", 
                placeholder="e.g., 12345",
                help="Enter the student ID exactly as it appears on their QR code"
            )
            
            if st.button("🔍 Process Student ID", type="primary"):
                if manual_id.strip():
                    process_student_scan(manual_id.strip(), sheet)
                else:
                    st.warning("Please enter a valid Student ID.")
        
        with col2:
            st.write("**Alternative QR Scanner:**")
            # Fallback to Streamlit's built-in camera
            fallback_image = st.camera_input("📷 Fallback Camera (if live camera fails)")
            
            if fallback_image:
                img = Image.open(fallback_image)
                st.image(img, caption="Captured Image", width=200)
                
                with st.spinner("🔍 Scanning QR code..."):
                    qr_data = detect_qr_with_opencv(img)
                
                if qr_data:
                    st.success(f"📋 **Scanned ID:** {qr_data}")
                    process_student_scan(qr_data, sheet)
                else:
                    st.error("⚠️ No QR code detected.")
    
    # JavaScript to handle postMessage from camera component
    st.markdown("""
    <script>
    window.addEventListener('message', function(event) {
        if (event.data.type === 'captured_image') {
            // Store captured image data in Streamlit session state
            window.parent.postMessage({
                type: 'streamlit:setComponentValue',
                data: {
                    captured_image_data: event.data.data
                }
            }, '*');
        }
    });
    </script>
    """, unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: #666;'>🏫 Orientation Management System | Live Camera QR Scanner</p>", 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
