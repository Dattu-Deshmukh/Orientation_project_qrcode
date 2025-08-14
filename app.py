import streamlit as st
from pyzbar.pyzbar import decode
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from PIL import Image
import io

# ========================
# GOOGLE SHEETS CONNECTION
# ========================
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Open your sheet
sheet = client.open("orientation_passes").sheet1

# ========================
# STREAMLIT UI
# ========================
st.set_page_config(page_title="Orientation QR Scanner", page_icon="📷", layout="centered")

st.markdown("<h1 style='text-align:center; color:#4CAF50;'>🎓 Orientation QR Scanner</h1>", unsafe_allow_html=True)
st.write("📌 Scan the student's QR code to mark **entry** and **exit**.")

# Camera input for mobile
image_data = st.camera_input("📷 Scan QR Code")

if image_data:
    # Read the image
    img = Image.open(image_data)
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes = img_bytes.getvalue()

    # Decode QR
    decoded_objs = decode(Image.open(io.BytesIO(img_bytes)))

    if not decoded_objs:
        st.error("⚠ No QR code detected. Try again.")
    else:
        qr_data = decoded_objs[0].data.decode("utf-8")
        st.info(f"Scanned ID: **{qr_data}**")

        try:
            records = sheet.get_all_records()
            found = False

            for i, row in enumerate(records, start=2):
                if str(row["ID"]) == qr_data:
                    found = True
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # Mark entry
                    if row["EntryStatus"] == "":
                        sheet.update_cell(i, 4, "Entered")
                        sheet.update_cell(i, 5, now)
                        st.success(f"✅ Entry marked for **{row['Name']}** ({row['Branch']})")

                    # Mark exit
                    elif row["ExitStatus"] == "":
                        sheet.update_cell(i, 6, "Exited")
                        sheet.update_cell(i, 7, now)
                        st.warning(f"🚪 Exit marked for **{row['Name']}** ({row['Branch']})")

                    else:
                        st.info(f"ℹ️ {row['Name']} ({row['Branch']}) already entered and exited.")

                    break

            if not found:
                st.error("❌ ID not found in records.")

        except Exception as e:
            st.error(f"Error: {e}")
