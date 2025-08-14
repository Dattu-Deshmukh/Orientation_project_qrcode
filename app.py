import streamlit as st
from datetime import datetime
from PIL import Image
import io
import numpy as np
import base64
import time

# Handle optional imports gracefully
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    st.error("❌ Google Sheets integration not available. Please install: pip install gspread oauth2client")
    GSPREAD_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    st.warning("⚠️ OpenCV not available. QR detection may be limited. Install with: pip install opencv-python-headless")
    CV2_AVAILABLE = False

# ========================
# QR CODE DETECTION FUNCTIONS
# ========================

def detect_qr_with_opencv(image):
    """Try to detect QR code using OpenCV"""
    if not CV2_AVAILABLE:
        st.error("OpenCV not available for QR detection")
        return None
        
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
            <button onclick="switchCamera()" style="background-color: #2196F3; color: white; padding: 12px 20px; border: none; border-radius: 8px; margin: 5px; cursor: pointer; font-size: 16px;">
                🔄 Switch Camera
            </button>
            <button onclick="captureImage()" style="background-color: #4CAF50; color: white; padding: 12px 20px; border: none; border-radius: 8px; margin: 5px; cursor: pointer; font-size: 16px;">
                📸 Capture QR
            </button>
            <button onclick="toggleCamera()" id="toggleBtn" style="background-color: #FF9800; color: white; padding: 12px 20px; border: none; border-radius: 8px; margin: 5px; cursor: pointer; font-size: 16px;">
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
    let facingMode = 'environment'; // Start with rear camera (back camera)
    let isScanning = false;
    let cameraActive = false;

    // Start camera function
    async function startCamera() {
        try {
            if (currentStream) {
                currentStream.getTracks().forEach(track => track.stop());
            }

            // Try rear camera first with more specific constraints
            const constraints = {
                video: {
                    facingMode: { exact: facingMode },
                    width: { ideal: 1280, max: 1920 },
                    height: { ideal: 720, max: 1080 }
                }
            };

            try {
                currentStream = await navigator.mediaDevices.getUserMedia(constraints);
            } catch (err) {
                // Fallback if exact facingMode fails
                console.log('Exact facingMode failed, trying ideal...', err);
                const fallbackConstraints = {
                    video: {
                        facingMode: { ideal: facingMode },
                        width: { ideal: 1280 },
                        height: { ideal: 720 }
                    }
                };
                currentStream = await navigator.mediaDevices.getUserMedia(fallbackConstraints);
            }

            video.srcObject = currentStream;
            cameraActive = true;
            document.getElementById('toggleBtn').innerHTML = '⏸️ Stop Camera';
            
            const cameraType = facingMode === 'environment' ? '📱 Rear Camera' : '🤳 Front Camera';
            document.getElementById('result').innerHTML = `<div style="color: green;">📹 ${cameraType} Active - Point at QR code and capture</div>`;
            
            // Start continuous QR scanning
            startContinuousScanning();
            
        } catch (error) {
            console.error('Error accessing camera:', error);
            document.getElementById('result').innerHTML = '<div style="color: red;">❌ Camera access denied or not available. Please allow camera permissions and try again.</div>';
        }
    }

    // Switch between front and rear camera
    async function switchCamera() {
        facingMode = facingMode === 'environment' ? 'user' : 'environment';
        const cameraType = facingMode === 'environment' ? '📱 Rear Camera' : '🤳 Front Camera';
        document.getElementById('result').innerHTML = `<div style="color: blue;">🔄 Switching to ${cameraType}...</div>`;
        
        // Small delay to show the switching message
        setTimeout(() => {
            startCamera();
        }, 500);
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

        if (video.videoWidth === 0 || video.videoHeight === 0) {
            document.getElementById('result').innerHTML = '<div style="color: red;">❌ Camera not ready. Please wait a moment and try again.</div>';
            return;
        }

        // Set canvas dimensions to match video
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // Draw current video frame to canvas
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Convert to base64 and send to Streamlit
        const imageData = canvas.toDataURL('image/png');
        document.getElementById('result').innerHTML = '<div style="color: orange;">🔍 Processing image for QR code...</div>';
        
        // Create a custom event to communicate with Streamlit
        const event = new CustomEvent('qr_image_captured', {
            detail: { imageData: imageData }
        });
        
        // Dispatch the event
        window.dispatchEvent(event);
        
        // Also try the postMessage approach as backup
        if (window.parent) {
            window.parent.postMessage({
                type: 'captured_image',
                data: imageData
            }, '*');
        }
        
        // Store in window object as another fallback
        window.capturedQRImage = imageData;
        
        console.log('Image captured and stored');
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

    // Auto-start camera when page loads with rear camera
    window.addEventListener('load', () => {
        // Ensure we start with rear camera
        facingMode = 'environment';
        setTimeout(() => {
            document.getElementById('result').innerHTML = '<div style="color: orange;">📷 Starting rear camera...</div>';
            startCamera();
        }, 1000);
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
    if not GSPREAD_AVAILABLE:
        st.error("Google Sheets integration not available. Please install required packages.")
        return None
        
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
    if not GSPREAD_AVAILABLE:
        st.error("❌ **Google Sheets integration not available**")
        st.info("To enable Google Sheets functionality, please ensure these packages are installed:")
        st.code("pip install gspread oauth2client")
        st.stop()
    
    sheet = init_google_sheets()
    if not sheet:
        st.stop()
    
    # Create tabs for different input methods
    tab1, tab2 = st.tabs(["📹 Live Camera Scanner", "📝 Manual Entry"])
    
    with tab1:
        st.write("### 📹 Live Camera QR Scanner")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            # Display the custom camera component
            camera_component = create_camera_component()
            st.components.v1.html(camera_component, height=650)
        
        with col2:
            # Image processing and results area
            st.write("### 🔍 Scan Results")
            
            # Check for captured images from multiple sources
            captured_image_data = None
            
            # Method 1: Check session state
            if 'captured_qr_image' in st.session_state:
                captured_image_data = st.session_state.captured_qr_image
                del st.session_state.captured_qr_image
            
            # Method 2: Check if there's a rerun trigger
            if st.button("🔄 Check for Captured Image", key="check_capture"):
                st.rerun()
            
            # Process captured image if available
            if captured_image_data:
                try:
                    # Decode base64 image
                    if captured_image_data.startswith('data:image'):
                        base64_data = captured_image_data.split(',')[1]
                        image_bytes = base64.b64decode(base64_data)
                        
                        # Convert to PIL Image
                        img = Image.open(io.BytesIO(image_bytes))
                        
                        st.image(img, caption="📸 Captured Image", width=300)
                        
                        with st.spinner("🔍 Scanning for QR code..."):
                            qr_data = detect_qr_with_opencv(img)
                        
                        if qr_data:
                            st.success(f"📋 **Scanned ID:** {qr_data}")
                            process_student_scan(qr_data, sheet)
                        else:
                            st.error("⚠️ **No QR code detected** in the image.")
                            st.write("Try adjusting the camera angle or lighting.")
                
                except Exception as e:
                    st.error(f"Error processing captured image: {e}")
            
            else:
                st.info("📷 Point camera at QR code and click 'Capture QR' button")
                
                # Show a placeholder for captured images
                st.empty()
        
        # Instructions section moved here - after the camera and scan results
        st.write("---")
        st.write("### 📋 Camera Instructions & Tips")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("""
            **🎯 Camera Controls:**
            - 🔄 **Switch Camera**: Toggle front/rear
            - 📸 **Capture QR**: Take photo to scan
            - ⏸️ **Stop Camera**: Turn off camera
            
            **📱 Current Mode:**
            - **Default: Rear Camera** 
            - Better for QR code scanning
            """)
        
        with col2:
            st.success("""
            **✅ Scanning Tips:**
            - Ensure good lighting
            - Hold phone steady
            - QR code should fill most of frame
            - Try switching cameras if one doesn't work
            - Wait for camera to focus before capturing
            """)
        
        # Troubleshooting section
        with st.expander("🔧 Troubleshooting"):
            st.write("""
            **If capture is not working:**
            1. Wait 2-3 seconds after camera starts
            2. Ensure QR code is clearly visible
            3. Try the 'Switch Camera' button
            4. Check browser camera permissions
            5. Use 'Manual Entry' tab as backup
            
            **If camera won't start:**
            1. Refresh the page
            2. Allow camera permissions in browser
            3. Try a different browser (Chrome/Safari recommended)
            4. Check if another app is using the camera
            """)
        
        # Auto-refresh mechanism to check for captures
        if st.button("🔄 Refresh to Check Captures", key="auto_refresh"):
            st.rerun()
    
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
            st.write("**📸 Alternative Methods:**")
            
            # File uploader as another option
            uploaded_file = st.file_uploader(
                "Upload QR Code Image", 
                type=['png', 'jpg', 'jpeg'],
                help="Upload a photo of the QR code if camera scanning fails"
            )
            
            if uploaded_file:
                img = Image.open(uploaded_file)
                st.image(img, caption="Uploaded Image", width=200)
                
                with st.spinner("🔍 Scanning uploaded QR code..."):
                    qr_data = detect_qr_with_opencv(img)
                
                if qr_data:
                    st.success(f"📋 **Scanned ID:** {qr_data}")
                    process_student_scan(qr_data, sheet)
                else:
                    st.error("⚠️ No QR code detected in uploaded image.")
            
            st.write("**📷 Backup Camera:**")
            # Fallback to Streamlit's built-in camera
            fallback_image = st.camera_input("Fallback Camera (if live camera fails)")
            
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
    
    # Enhanced JavaScript to handle captured images better
    st.markdown("""
    <script>
    // Handle postMessage from camera component
    window.addEventListener('message', function(event) {
        if (event.data && event.data.type === 'captured_image') {
            console.log('Received captured image via postMessage');
            // Trigger Streamlit to update with captured image
            window.capturedImageForStreamlit = event.data.data;
        }
    });
    
    // Handle custom events
    window.addEventListener('qr_image_captured', function(event) {
        console.log('Received captured image via custom event');
        window.capturedImageForStreamlit = event.detail.imageData;
    });
    
    // Check for captured images periodically
    setInterval(function() {
        if (window.capturedQRImage || window.capturedImageForStreamlit) {
            console.log('Found captured image, triggering Streamlit update');
            // You can trigger a Streamlit rerun here if needed
        }
    }, 1000);
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
