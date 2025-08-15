import streamlit as st
from datetime import datetime
from PIL import Image
import io
import numpy as np

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
        page_title="NREC Orientation QR Scanner", 
        page_icon="🎓", 
        layout="wide"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        color: #4CAF50;
        font-size: 2.8rem;
        margin-bottom: 0.5rem;
        font-weight: bold;
    }
    .college-header {
        text-align: center;
        color: #2196F3;
        font-size: 1.5rem;
        margin-bottom: 1rem;
        font-style: italic;
    }
    .orientation-banner {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
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
    
    # College Header
    st.markdown('<h1 class="main-header">🎓 Orientation QR Scanner</h1>', unsafe_allow_html=True)
    st.markdown('<h2 class="college-header">Narsimha Reddy Engineering College</h2>', unsafe_allow_html=True)
    
    # Orientation Day Banner
    st.markdown("""
    <div class="orientation-banner">
        <h2>🎉 Welcome to Orientation Day!</h2>
        <h3>📅 August 18th, 2025</h3>
        <p><strong>Dear Students,</strong> Welcome to Narsimha Reddy Engineering College! 
        This QR scanner will help track your attendance for today's orientation program.</p>
        <p>🕐 <strong>Program Schedule:</strong> Registration → Welcome Session → Campus Tour → Department Introduction</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="instruction-box">
    📌 <strong>Orientation Day Instructions:</strong><br>
    1. Scan your student QR code for <strong>Entry</strong> when you arrive<br>
    2. Participate in all orientation activities<br>
    3. Scan again for <strong>Exit</strong> when leaving<br>
    4. Keep your student ID card ready for verification<br>
    5. Contact orientation volunteers if you need assistance
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
    tab1, tab2 = st.tabs(["📱 QR Camera Scanner", "📝 Manual Entry"])
    
    with tab1:
        st.write("### 📱 Camera QR Scanner")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            # Primary Camera Scanner (using working Streamlit camera)
            st.write("#### 📷 Scan QR Code")
            camera_image = st.camera_input(
                "Point camera at student's QR code and take photo",
                help="For best results: ensure good lighting, hold steady, QR code fills frame"
            )
            
            if camera_image:
                img = Image.open(camera_image)
                st.image(img, caption="📸 Captured QR Code", width=400)
                
                with st.spinner("🔍 Scanning for QR code..."):
                    qr_data = detect_qr_with_opencv(img)
                
                if qr_data:
                    st.success(f"📋 **Scanned Student ID:** {qr_data}")
                    process_student_scan(qr_data, sheet)
                else:
                    st.error("⚠️ **No QR code detected** in the image.")
                    st.write("**Try again with:**")
                    st.write("• Better lighting")
                    st.write("• QR code fully visible in frame")
                    st.write("• Hold camera steady")
                    st.write("• Clean camera lens")
        
        with col2:
            # Scan Results and Status
            st.write("#### 🔍 Scan Status")
            
            if not camera_image:
                st.info("📷 **Ready to scan**\nPoint camera at QR code and capture photo")
            
            # Alternative upload option
            st.write("---")
            st.write("#### 📤 Alternative: Upload QR Image")
            uploaded_file = st.file_uploader(
                "Upload QR Code Photo", 
                type=['png', 'jpg', 'jpeg'],
                help="Upload a clear photo of the QR code if camera doesn't work"
            )
            
            if uploaded_file:
                img = Image.open(uploaded_file)
                st.image(img, caption="Uploaded QR Code", width=300)
                
                with st.spinner("🔍 Scanning uploaded QR code..."):
                    qr_data = detect_qr_with_opencv(img)
                
                if qr_data:
                    st.success(f"📋 **Scanned ID:** {qr_data}")
                    process_student_scan(qr_data, sheet)
                else:
                    st.error("⚠️ No QR code detected in uploaded image.")
        
        # Instructions section moved here - after the camera and scan results
        st.write("---")
        st.write("### 📋 Camera Scanning Tips")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info("""
            **📱 Camera Tips:**
            • Use rear camera if available
            • Ensure good lighting
            • Hold device steady
            • QR code should fill most of frame
            • Clean camera lens
            """)
        
        with col2:
            st.success("""
            **✅ For Best Results:**
            • Wait for camera to focus
            • Avoid shadows on QR code
            • Keep QR code flat and straight
            • Distance: 6-12 inches away
            • Try different angles if needed
            """)
            
        with col3:
            st.warning("""
            **⚠️ Troubleshooting:**
            • Refresh page if camera fails
            • Allow camera permissions
            • Try different browser
            • Use file upload as backup
            • Contact tech support if issues persist
            """)
        
        # Orientation Day Information
        st.write("---")
        st.write("### 🎓 Orientation Day Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("""
            **📅 Today's Schedule - August 18th:**
            • 9:00 AM - Registration & Check-in
            • 10:00 AM - Welcome Address
            • 11:00 AM - Campus Tour
            • 12:30 PM - Lunch Break
            • 2:00 PM - Department Introductions
            • 4:00 PM - Student Activities Fair
            • 5:30 PM - Closing & Check-out
            """)
            
        with col2:
            st.success("""
            **🏫 Important Reminders:**
            • Bring your admission documents
            • Carry student ID card
            • Scan QR code for entry AND exit
            • Follow COVID protocols if applicable
            • Ask volunteers for help
            • Join your department WhatsApp group
            """)
        
        # Emergency contact
        st.error("""
        **🆘 Need Help?**
        Contact Orientation Help Desk: **+91-XXXX-XXXXXX** | Email: **orientation@nrec.edu.in**
        """)

    with tab2:
        st.write("### 📝 Manual Student ID Entry")
        st.info("Use this option if camera scanning is not available or as a backup method.")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.write("#### ✏️ Enter Student Details")
            manual_id = st.text_input(
                "Student ID:", 
                placeholder="e.g., 2025001",
                help="Enter the student ID exactly as shown on the QR code or ID card"
            )
            
            if st.button("🔍 Process Student Entry/Exit", type="primary", use_container_width=True):
                if manual_id.strip():
                    process_student_scan(manual_id.strip(), sheet)
                else:
                    st.warning("⚠️ Please enter a valid Student ID.")
        
        with col2:
            st.write("#### 📊 Manual Entry Guidelines")
            st.success("""
            **✅ When to use Manual Entry:**
            • Camera not working
            • QR code damaged/unreadable
            • Student forgot QR code
            • Technical issues with scanning
            • Backup verification needed
            """)
            
            st.info("""
            **📝 ID Format Examples:**
            • NRCM2025001 (Regular format)
            • 2025CSE001 (Department wise)
            • Or any format in your system
            """)
        
        # Quick stats or recent entries (optional)
        st.write("---")
        st.write("#### 📈 Today's Orientation Stats")
        
        # You can add real-time stats here
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🟢 Entries Today", "- -", help="Students who have checked in")
        
        with col2:
            st.metric("🔄 Currently Present", "- -", help="Students currently in orientation")
        
        with col3:
            st.metric("🟡 Exits Today", "- -", help="Students who have checked out")
    
    # Footer with college information
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px; background-color: #f8f9fa; border-radius: 10px;">
        <h4>🏫 Narsimha Reddy Engineering College</h4>
        <p><strong>Orientation Day - August 18th, 2025</strong></p>
        <p style="font-size: 12px; margin-top: 15px;">
            © 2025 NRCM - School of Computer Science 
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
